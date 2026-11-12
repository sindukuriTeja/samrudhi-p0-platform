"""Project runner — a thin layer over the existing agents.

It walks the documented chain (config/project_flows.yaml) in order. For each step:
  1. refuses to run an agent that is not Active (lifecycle state active/monitored)
  2. checks the step's permission with the existing authority guard
  3. runs the step:
       think - dispatches the existing Celery task workers.tasks.run_agent_task
       tool  - calls the agent's own authority-guarded tool in code and logs it
       skip  - records why the step has nothing real to work on
  4. stores the result: a readable message, and a structured result for later steps
  5. applies the documented control flow: checker send-backs (rework rounds through
     Punargathan with a round limit) and human gates (approvals table)

It contains no agent logic and never calls the model directly. Human decisions are
written only by the API endpoint for a signed-in user.
"""
import asyncio
import json
import logging
import re
import uuid

from sqlalchemy import func, select, update

from backend.core.authority import AuthorityError, check_authority
from backend.core.message_bus import BusEnvelope, bus
from backend.database import async_session_maker
from backend.models import Agent, Approval, ExecutionLog
from backend.models.projects import ApprovalDecision, ApprovalSignoff, Project, ProjectMessage, ProjectStep
from backend.core import safety_rules
from backend.core import knowledge as kn
from backend.core import tenancy
from backend.models.knowledge import ClientProfile, KnowledgeSource
from backend.projects import dispatch as dispatcher
from backend.projects import registers
from backend.projects import schema
from backend.projects.common import (
    ENDED_PROJECT_STATES, RUNNABLE_STATES, new_approval_id, utcnow,
)
from backend.projects.events import notify, redis_alive
from backend.projects.flow import (
    chain_permissions, checks_between, get_flow, required_agents, running_steps,
    step_def, step_permission,
)
from backend.projects.readable import one_line, readable

log = logging.getLogger("samrudhi.projects")

MODEL_UNAVAILABLE = "[MODEL UNAVAILABLE]"
INPUT_CHARS = 800
VERDICT_RE = re.compile(r"VERDICT\s*[:\-]\s*(PASS|SEND[\s\-]*BACK)\b[\s:\-–—]*(.*)", re.I | re.S)


class ProjectError(Exception):
    def __init__(self, status: int, detail):
        super().__init__(str(detail))
        self.status = status
        self.detail = detail


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _project(s, pid: str) -> Project:
    p = await s.get(Project, pid)
    if p is None:
        raise ProjectError(404, f"Project {pid} not found")
    return p


async def _agent_names(s) -> dict[str, str]:
    rows = (await s.execute(select(Agent.canonical_id, Agent.name))).all()
    return {cid: name for cid, name in rows}


def _sys_msg(pid: str, text: str, kind: str = "system", step_id: int | None = None) -> ProjectMessage:
    return ProjectMessage(project_id=pid, author_type="system", kind=kind, text=text, step_id=step_id)


async def pending_approval(s, pid: str) -> Approval | None:
    q = (
        select(Approval)
        .join(ProjectStep, ProjectStep.approval_id == Approval.request_id)
        .where(ProjectStep.project_id == pid, Approval.decision.is_(None))
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def open_issues(s, pid: str) -> list[ProjectStep]:
    """Steps still in progress or needing attention that have not been superseded by a later round."""
    steps = (await s.execute(select(ProjectStep).where(
        ProjectStep.project_id == pid).order_by(ProjectStep.seq))).scalars().all()
    issues = []
    for i, st in enumerate(steps):
        if st.status not in ("in_progress", "needs_attention"):
            continue
        if not any(o.step_key == st.step_key for o in steps[i + 1:]):
            issues.append(st)
    return issues


async def _insert_rounds(s, pid: str, after_seq: int, step_keys: list[str], flow: dict,
                         source_approval_id: str | None, prefill: dict | None = None) -> list[ProjectStep]:
    """Insert new rounds of the given step keys right after after_seq. Earlier rounds are kept."""
    n = len(step_keys)
    await s.execute(
        update(ProjectStep)
        .where(ProjectStep.project_id == pid, ProjectStep.seq > after_seq)
        .values(seq=ProjectStep.seq + n)
    )
    created = []
    production = set(_production_keys(flow))
    for i, key in enumerate(step_keys, start=1):
        d = step_def(flow, key)
        latest_any = (await s.execute(select(ProjectStep).where(
            ProjectStep.project_id == pid, ProjectStep.step_key == key)
            .order_by(ProjectStep.seq.desc()).limit(1))).scalars().first()
        if key in production and latest_any is not None and latest_any.status == "skipped" \
                and not (latest_any.result_json or {}).get("_packages"):
            continue  # Vitaran assigned this producer no packages: no new round either
        carry = {}
        if latest_any is not None and (latest_any.result_json or {}).get("_packages") is not None:
            carry["_packages"] = latest_any.result_json["_packages"]
        max_round = (await s.execute(
            select(func.max(ProjectStep.round)).where(
                ProjectStep.project_id == pid, ProjectStep.step_key == key)
        )).scalar() or 0
        st = ProjectStep(
            project_id=pid, seq=after_seq + i, step_key=key, agent_id=d["agent"],
            responsibility=d["responsibility"], tag=d["tag"], round=max_round + 1,
            status="queued", source_approval_id=source_approval_id,
            result_json={**carry, **dict((prefill or {}).get(key) or {})} or None,
        )
        s.add(st)
        created.append(st)
    return created


async def _latest(s, pid: str, key: str, completed_only: bool = True) -> ProjectStep | None:
    q = select(ProjectStep).where(ProjectStep.project_id == pid, ProjectStep.step_key == key)
    if completed_only:
        q = q.where(ProjectStep.status == "completed")
    return (await s.execute(q.order_by(ProjectStep.seq.desc()).limit(1))).scalars().first()


async def _output(s, pid: str, key: str) -> str:
    st = await _latest(s, pid, key)
    if st is None:
        return ""
    msg = (await s.execute(select(ProjectMessage).where(
        ProjectMessage.step_id == st.id, ProjectMessage.author_type == "agent"
    ).order_by(ProjectMessage.id.desc()).limit(1))).scalars().first()
    return msg.text if msg else ""


async def _human_texts(s, pid: str) -> list[str]:
    rows = (await s.execute(select(ProjectMessage).where(
        ProjectMessage.project_id == pid, ProjectMessage.author_type == "human",
        ProjectMessage.kind.in_(("start", "message")),
    ).order_by(ProjectMessage.created_at, ProjectMessage.id))).scalars().all()
    return [m.text for m in rows]


def _scope(flow: dict, human_texts: list[str]) -> dict:
    scope = dict((flow.get("defaults") or {}).get("scope") or {"social_posts": 3})
    for text in human_texts:
        m = re.search(r"\b(\d{1,2})\s+(?:short\s+|simple\s+|social\s+(?:media\s+)?)*posts?\b", text, re.I)
        if m:
            scope["social_posts"] = int(m.group(1))
    return scope


def _production_keys(flow: dict) -> list[str]:
    return list((flow.get("defaults") or {}).get("production_steps") or [])


async def _production_plan(s, pid: str, flow: dict) -> list[dict]:
    """Vitaran's assignments turned into one entry per producing step, with Samay's due dates."""
    assign = await _latest(s, pid, "assignments")
    rows = ((assign.result_json or {}) if assign else {}).get("assignments") or []
    names = await _agent_names(s)
    plan = []
    for key in _production_keys(flow):
        d = step_def(flow, key)
        if d is None:
            continue
        pkgs = [{"package_id": r.get("package_id"), "type": r.get("type"), "sequence": r.get("sequence"),
                 "due_date": r.get("due_date")} for r in rows if d["agent"] in (r.get("assigned_to") or [])]
        if pkgs:
            plan.append({"step": key, "agent": d["agent"], "agent_name": names.get(d["agent"], d["agent"]),
                         "tag": d["tag"], "packages": pkgs})
    return plan


async def _gate_decision(s, pid: str, key: str) -> dict:
    """The human decision on the latest gate step `key` ({"decision": None} if none yet)."""
    st = await _latest(s, pid, key, completed_only=False)
    if st is None or not st.approval_id:
        return {"decision": None, "decided_by": None}
    dec = (await s.execute(select(ApprovalDecision).where(
        ApprovalDecision.request_id == st.approval_id))).scalars().first()
    if dec is None:
        return {"request_id": st.approval_id, "decision": None, "decided_by": None}
    signs = (await s.execute(select(ApprovalSignoff).where(ApprovalSignoff.request_id == st.approval_id)
                             .order_by(ApprovalSignoff.decided_at))).scalars().all()
    return {"request_id": st.approval_id, "decision": dec.decision, "decided_by": dec.decided_by,
            "decided_at": dec.decided_at.isoformat() if dec.decided_at else None,
            "signed_by": [{"party": r.party, "by": r.decided_by, "decision": r.decision} for r in signs]}


def profile_out(cp: ClientProfile) -> dict:
    return {"client_id": cp.client_id, "name": cp.name, "brand_voice": cp.brand_voice, "audience": cp.audience,
            "services": list(cp.services or []), "locations": list(cp.locations or []),
            "key_messages": list(cp.key_messages or []), "status": cp.status, "version": cp.version,
            "updated_by": cp.updated_by, "updated_at": cp.updated_at.isoformat() if cp.updated_at else None,
            "approved_by": cp.approved_by, "approved_at": cp.approved_at.isoformat() if cp.approved_at else None}


async def _client_profile(s, client_id: str) -> dict | None:
    cp = await s.get(ClientProfile, client_id)
    return profile_out(cp) if cp else None


async def _approved_sources(s, client_id: str) -> list[dict]:
    """Approved sources this client may use: its own and the shared library."""
    rows = (await s.execute(select(KnowledgeSource).where(
        KnowledgeSource.status == "approved",
        (KnowledgeSource.client_id == client_id) | (KnowledgeSource.client_id.is_(None))))).scalars().all()
    return [{"id": r.id, "title": r.title, "publisher": r.publisher, "url": r.url,
             "topics": list(r.topics or []), "text": r.text} for r in rows]


async def _library_query(s, p: Project) -> str:
    """What the research is about: the project, the human instructions, the brief and the creative request."""
    parts = [p.name] + await _human_texts(s, p.id)
    for key in ("brief", "creative_request", "client_expectations"):
        st = await _latest(s, p.id, key)
        if st is not None:
            parts.append(schema.flatten_text(schema.public(st.result_json)))
    return " ".join(parts)


async def _foreign_data(s, p: Project, data) -> list[str]:
    """Other clients' ids or names found in data about to be handed to an agent (tenant isolation)."""
    clients: dict[str, list[str]] = {}
    for cid, info in (safety_rules._load().get("clients") or {}).items():
        clients.setdefault(cid, []).extend([(info or {}).get("name")] + list((info or {}).get("aliases") or []))
    for cid, name in (await s.execute(select(ClientProfile.client_id, ClientProfile.name))).all():
        clients.setdefault(cid, []).append(name)
    marks = tenancy.markers(p.client_id, [(c, [n for n in ns if n]) for c, ns in clients.items()])
    return tenancy.find_foreign(data, marks)


async def _safety_findings(s, p: Project, posts_from: str = "writing", evidence_from: str | None = "research",
                           only: set | None = None) -> tuple[list[dict], int]:
    """Check the latest posts against the client's safety rules (config/safety_rules.yaml)."""
    src = await _latest(s, p.id, posts_from)
    posts = ((src.result_json or {}) if src else {}).get("posts") or []
    evidence = None
    if evidence_from:
        ev = await _latest(s, p.id, evidence_from)
        data = schema.public(ev.result_json) if ev else {}
        facts = data.get("facts") if isinstance(data, dict) else None
        if isinstance(facts, list) and any(isinstance(f, dict) and "verified" in f for f in facts):
            # only facts verified against an approved source count as evidence
            evidence = "\n".join(f"{f.get('fact', '')} {f.get('quote', '')}" for f in facts
                                  if isinstance(f, dict) and f.get("verified"))
        else:
            evidence = schema.flatten_text(data) if data else ""
    res = safety_rules.screen(posts, safety_rules.rules_for(p.client_id), evidence=evidence, only=only)
    return res["findings"], res["posts_checked"]


def _passed(st: ProjectStep | None) -> bool:
    return bool(st is not None and st.status == "completed" and (st.result_json or {}).get("_passed", True))


async def _checks(s, pid: str, flow: dict) -> dict:
    required = (flow.get("defaults") or {}).get("required_checks") or []
    out = {}
    for key in required:
        st = await _latest(s, pid, key, completed_only=False)
        out[key] = _passed(st)
    return out


async def _resolve(value, s, p: Project, step: ProjectStep, flow: dict):
    if isinstance(value, dict):
        return {k: await _resolve(v, s, p, step, flow) for k, v in value.items()}
    if isinstance(value, list):
        return [await _resolve(v, s, p, step, flow) for v in value]
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    defaults = flow.get("defaults") or {}
    name = value[1:]
    if name.startswith("result:"):
        key, _, field = name[len("result:"):].partition(".")
        st = await _latest(s, p.id, key)
        return ((st.result_json or {}) if st else {}).get(field)
    if name.startswith("output:"):
        return await _output(s, p.id, name[len("output:"):])
    if name.startswith("text:") or name.startswith("data:"):
        key = name.split(":", 1)[1]
        st = await _latest(s, p.id, key)
        data = schema.public(st.result_json) if st else {}
        if name.startswith("data:"):
            return data
        return schema.flatten_text(data) if data else await _output(s, p.id, key)
    if name == "metrics":
        from backend.projects.metrics import project_metrics
        return await project_metrics(s, p.id)
    if name in ("cost_rates", "currency", "kpi_targets"):
        from backend.core import costing
        cfg = costing.config()
        return {"cost_rates": cfg.get("rates") or {}, "currency": cfg.get("currency"),
                "kpi_targets": cfg.get("kpis") or {}}[name]
    if name == "client_profile":
        return await _client_profile(s, p.client_id)
    if name == "client_rules":
        return safety_rules.rules_for(p.client_id)
    if name.startswith("safety:"):
        return safety_rules.rules_for(p.client_id).get(name[len("safety:"):])
    if name.startswith("gate:"):
        return await _gate_decision(s, p.id, name[len("gate:"):])
    if name.startswith("safety_check:"):
        findings, n = await _safety_findings(s, p, name[len("safety_check:"):])
        return {"passed": not findings and n > 0, "posts_checked": n,
                "findings": [safety_rules.describe(f) for f in findings] or ([] if n else ["there are no posts"])}
    if name == "project_id":
        return p.id
    if name == "project_name":
        return p.name
    if name == "client_id":
        return p.client_id
    if name == "today":
        return utcnow().date().isoformat()
    if name == "scope":
        return _scope(flow, await _human_texts(s, p.id))
    if name == "active_agents":
        return list((await s.execute(select(Agent.canonical_id).where(
            Agent.status.in_(RUNNABLE_STATES)))).scalars().all())
    if name == "chain_permissions":
        return chain_permissions(flow)
    if name == "production_plan":
        return await _production_plan(s, p.id, flow)
    if name == "chain_steps":
        names = await _agent_names(s)
        return [f"{names.get(d['agent'], d['agent'])} · {d['tag']}" for d in flow["steps"]]
    if name == "checks":
        return await _checks(s, p.id, flow)
    if name == "tokens_total":
        return int((await s.execute(select(func.coalesce(func.sum(ExecutionLog.tokens_used), 0)).where(
            ExecutionLog.workflow_id == p.id))).scalar() or 0)
    if name == "model_steps":
        return int((await s.execute(select(func.count()).select_from(ExecutionLog).where(
            ExecutionLog.workflow_id == p.id, ExecutionLog.tokens_used > 0))).scalar() or 0)
    if name == "accepted_deliverables":
        gate = await _latest(s, p.id, "sweekriti")
        if gate is None or not gate.approval_id:
            return 0
        dec = (await s.execute(select(ApprovalDecision).where(
            ApprovalDecision.request_id == gate.approval_id))).scalars().first()
        if dec is None or dec.decision == "reject":
            return 0
        return sum(int(v) for v in _scope(flow, await _human_texts(s, p.id)).values())
    if name in ("send_back_reasons", "rework_round"):
        rj = step.result_json or {}
        return rj.get("pending_reasons", []) if name == "send_back_reasons" else rj.get("round", 1)
    if name in defaults:
        return defaults[name]
    return value


async def _decide_pass(d: dict, result: dict) -> bool:
    cond = d.get("pass_if")
    if not cond:
        return True
    return all(result.get(k) == v for k, v in cond.items())


def _fail_reasons(result: dict) -> list[str]:
    for k in ("findings", "flags", "reasons", "missing_checks", "missing", "missing_evidence", "defects", "denied",
              "unassigned"):
        v = result.get(k)
        if v:
            return [json.dumps(x) if isinstance(x, dict) else str(x) for x in v]
    return [str(result.get("status", "did not pass"))]


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

class ProjectRunner:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def kick(self, pid: str, resume_step_id: int | None = None, resume_ref: str | None = None) -> None:
        t = self._tasks.get(pid)
        if t is not None and not t.done():
            return
        self._tasks[pid] = asyncio.create_task(self._loop(pid, resume_step_id, resume_ref))

    def is_busy(self, pid: str) -> bool:
        t = self._tasks.get(pid)
        return t is not None and not t.done()

    async def shutdown(self) -> None:
        for t in list(self._tasks.values()):
            t.cancel()

    async def _loop(self, pid: str, resume_step_id: int | None, resume_ref: str | None) -> None:
        try:
            if resume_step_id is not None and resume_ref:
                result = await dispatcher.wait_celery(resume_ref, pending_timeout=120)
                if not await self._finish_think(pid, resume_step_id, result):
                    return
            while await self._advance(pid):
                pass
        except asyncio.CancelledError:
            raise
        except Exception as e:  # never leave a project silently stuck
            log.exception("Project runner failed for %s", pid)
            async with async_session_maker() as s:
                p = await s.get(Project, pid)
                if p is not None and p.status == "running":
                    p.status = "needs_attention"
                    s.add(_sys_msg(pid, f"The project runner hit an error and paused the project: {e}", "error"))
                    await s.commit()
            await notify("project", pid)

    async def _block(self, s, p: Project, st: ProjectStep, error: str) -> bool:
        st.status = "needs_attention"
        st.error = error
        st.ended_at = utcnow()
        if p.status == "running":
            p.status = "needs_attention"
        s.add(_sys_msg(p.id, error, "error", st.id))
        await s.commit()
        await notify("project", p.id)
        return False

    async def _advance(self, pid: str) -> bool:
        """Run the next queued step. Returns True if the loop should continue."""
        async with async_session_maker() as s:
            p = await s.get(Project, pid)
            if p is None or p.status != "running":
                return False
            if await pending_approval(s, pid):
                return False
            step = (await s.execute(
                select(ProjectStep)
                .where(ProjectStep.project_id == pid, ProjectStep.status == "queued")
                .order_by(ProjectStep.seq).limit(1)
            )).scalars().first()
            flow = get_flow(p.flow_key)

            if step is None:
                if await open_issues(s, pid):
                    return False
                p.status = "completed"
                p.ended_at = utcnow()
                s.add(_sys_msg(pid, "All steps are finished. The project is completed.", "completed"))
                await s.commit()
                await notify("project", pid)
                return False

            d = step_def(flow, step.step_key) or {"mode": "think", "tag": step.tag}
            mode = d.get("mode", "think")
            names = await _agent_names(s)
            agent_name = names.get(step.agent_id, step.agent_id)

            if mode == "skip":
                step.status = "skipped"
                step.started_at = step.ended_at = utcnow()
                step.summary = d.get("reason", "Skipped.")
                s.add(_sys_msg(pid, f"{agent_name} · {d['tag']}: skipped. {step.summary}", "skipped", step.id))
                await s.commit()
                await notify("project", pid)
                return True

            agent = (await s.execute(select(Agent).where(Agent.canonical_id == step.agent_id))).scalars().first()
            # Rule: an agent that is not Active must not run.
            if agent is None or agent.status not in RUNNABLE_STATES:
                state = agent.status if agent else "not registered"
                return await self._block(s, p, step, (
                    f"{agent_name} is not Active (state: {state}), so it was not run. "
                    f"Activate it on its agent page, then press Retry."))

            # Rule: permissions are enforced in code by the authority guard.
            permission = step_permission(d, step.round)
            try:
                if permission:
                    check_authority(step.agent_id, permission)
            except AuthorityError:
                return await self._block(s, p, step, (
                    f"Blocked by the authority guard: {agent_name} may not perform '{permission}'."))

            step.status = "in_progress"
            step.started_at = utcnow()
            step.ended_at = None
            step.error = None

            if mode == "tool":
                return await self._run_tool(s, p, step, d, flow)

            task_text, context = await self._build_task(s, p, step, d)
            foreign = await _foreign_data(s, p, context)
            if foreign:
                return await self._block(s, p, step, (
                    "Tenant isolation: the data for this step contains another client's information ("
                    + ", ".join(foreign) + "), so it was not run. Remove it, then press Retry."))
            await s.commit()
            step_id = step.id
            args = [step.agent_id, task_text, p.client_id, p.id]
            kwargs = {"action": d.get("action"), "context": context}
            if d.get("output"):
                kwargs["output_format"] = "json"
        await notify("project", pid)

        async def _on_ref(ref: str) -> None:
            async with async_session_maker() as s2:
                st = await s2.get(ProjectStep, step_id)
                if st is not None:
                    st.dispatch_ref = ref
                    await s2.commit()

        result = await dispatcher.dispatch(args, kwargs, _on_ref)
        return await self._finish_think(pid, step_id, result)

    async def _build_task(self, s, p: Project, step: ProjectStep, d: dict) -> tuple[str, dict]:
        names = await _agent_names(s)
        humans = await _human_texts(s, p.id)
        handed_over = []
        flow = get_flow(p.flow_key)
        for key in d.get("inputs") or []:
            src = await _latest(s, p.id, key)
            if src is None:
                continue
            data = schema.public(src.result_json)
            item = {"from": names.get(src.agent_id, src.agent_id),
                    "step": (step_def(flow, key) or {}).get("tag", key)}
            if data:
                item["record"] = schema.trim(data)          # the whole structured record
            else:
                text = await _output(s, p.id, key)
                if not text:
                    continue
                item["result"] = (text[:INPUT_CHARS] + "…") if len(text) > INPUT_CHARS else text
            handed_over.append(item)
        note = (step.result_json or {}).get("revision_note")
        if step.source_approval_id and not note:
            dec = (await s.execute(select(ApprovalDecision).where(
                ApprovalDecision.request_id == step.source_approval_id))).scalars().first()
            note = dec.note if dec else None
        previous_own = ""
        if step.round > 1:
            prev = await _latest(s, p.id, step.step_key)
            prev_data = schema.public(prev.result_json) if prev else {}
            previous_own = json.dumps(prev_data, ensure_ascii=False) if prev_data else await _output(s, p.id, step.step_key)

        parts = [d.get("instruction", "").strip(), f"Project: {p.name}."]
        if humans:
            parts.append("Instructions from the human team: " + " | ".join(humans))
        if note:
            parts.append(f"This is round {step.round}. Revise your earlier work using this feedback: {note}")
        if d.get("output"):
            shape = json.dumps(schema.example(d["output"]), ensure_ascii=False)
            parts.append("Answer with ONE JSON object in exactly this shape (same keys; lists may hold as many "
                         f"items as needed): {shape}. Write \"unavailable\" for anything you do not know.")
            count = await self._expected_count(s, p, d, step)
            if count:
                parts.append(f"The list \"{d['count']['field']}\" must contain exactly {count} items, one per post.")
            if d.get("verdict"):
                parts.append('Set "verdict" to "pass" or "send_back", and give the reasons in "reasons".')
            errs = (step.result_json or {}).get("_format_errors")
            if errs:
                parts.append("Your previous answer was not accepted: " + "; ".join(errs) + ". Fix these.")
        elif d.get("verdict"):
            parts.append("End your answer with one final line: VERDICT: PASS, or VERDICT: SEND BACK - <short reasons>.")
        context = {
            "project_id": p.id, "project": p.name, "client_id": p.client_id,
            "step": d.get("tag"), "round": step.round,
            "human_instructions": humans, "handed_over": handed_over,
        }
        if d.get("library"):
            lib = kn.retrieve(await _library_query(s, p), await _approved_sources(s, p.client_id))
            context["source_library"] = lib
            if lib:
                parts.insert(1, "Use ONLY the approved sources in source_library. For every fact give its "
                                "source_id (for example " + lib[0]["passages"][0]["passage_id"] + ") and copy "
                                "the exact sentence you rely on into quote. A fact whose quote is not in that "
                                "source is marked not verified by code.")
            else:
                parts.insert(1, "No approved source in the library matches this project, so every fact will be "
                                "marked not verified. Write source_id \"none\" and quote \"unavailable\".")
        if d.get("code_rules"):
            # Tell the reviewer what the code has already verified, so it does not repeat (or
            # contradict) a check the code makes exactly.
            cr = d["code_rules"]
            found, n = await _safety_findings(s, p, cr.get("posts_from", "writing"), cr.get("evidence_from"))
            summary = safety_rules.code_summary(found, n, safety_rules.rules_for(p.client_id))
            if summary:
                context["code_checked"] = summary
                parts.insert(1, summary)
        if d.get("safety_rules") and not d.get("code_rules"):
            rules_text = safety_rules.prompt_text(safety_rules.rules_for(p.client_id))
            if rules_text:
                context["safety_rules"] = rules_text
                parts.insert(1, "Client safety rules (checked by code after you; breaking one sends the work "
                                "back): " + rules_text)
        packages = (step.result_json or {}).get("_packages")
        if packages:
            context["work_packages"] = packages
            parts.insert(1, f"You were assigned {len(packages)} work package(s) by Vitaran (see work_packages). "
                            "Produce exactly one item per package, in package order, ready by its due date.")
        if previous_own:
            context["your_previous_round"] = previous_own[:INPUT_CHARS]
        if note:
            context["revision_note"] = note
        return "\n".join(x for x in parts if x), context

    async def _expected_count(self, s, p: Project, d: dict, step: ProjectStep | None = None) -> int | None:
        rule = d.get("count")
        if not rule:
            return None
        packages = (step.result_json or {}).get("_packages") if step is not None else None
        if packages is not None:
            return len(packages)
        scope = _scope(get_flow(p.flow_key), await _human_texts(s, p.id))
        return int(scope.get(rule.get("scope", "social_posts"), 0)) or None

    async def _run_tool(self, s, p: Project, step: ProjectStep, d: dict, flow: dict) -> bool:
        from agents.base import get_agent_module
        args = await _resolve(d.get("args") or {}, s, p, step, flow)
        foreign = await _foreign_data(s, p, args)
        if foreign:
            return await self._block(s, p, step, (
                "Tenant isolation: the data for this step contains another client's information ("
                + ", ".join(foreign) + "), so it was not run. Remove it, then press Retry."))
        started = utcnow()
        try:
            result = getattr(get_agent_module(step.agent_id), d["method"])(**args)
            error = None
        except AuthorityError as e:
            result, error = None, f"Blocked by the authority guard: {e}"
        except Exception as e:
            result, error = None, f"{d['tag']} failed: {e}"
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        s.add(ExecutionLog(
            execution_id=execution_id, agent_id=step.agent_id, workflow_id=p.id,
            task=f"{d['tag']} ({d['method']})", tenant_id=p.client_id,
            status="completed" if error is None else "failed", tokens_used=0,
            started_at=started, ended_at=utcnow(), trace_id=uuid.uuid4().hex[:12],
            error=error, raw_result=result if isinstance(result, dict) else None,
        ))
        step.execution_id = execution_id
        if error:
            return await self._block(s, p, step, error)
        return await self._complete(s, p, step, d, flow, result, json.dumps(result, default=str),
                                    passed=await _decide_pass(d, result))

    async def _finish_think(self, pid: str, step_id: int, result: dict) -> bool:
        output = result.get("output") if isinstance(result, dict) else None
        status = result.get("status") if isinstance(result, dict) else "failed"
        err = None
        if status != "completed":
            err = result.get("error") or "The agent run failed without a reason."
        elif not isinstance(output, str) or not output.strip():
            err = "The agent finished but returned no result."
        elif output.strip().startswith(MODEL_UNAVAILABLE):
            err = ("Model unavailable: the local model (Ollama) is not running or did not answer in time, "
                   "so nothing was produced for this step.")
        if err and "Connect" in err and "Model unavailable" not in err:
            err = f"Model unavailable: {err}"

        async with async_session_maker() as s:
            p = await s.get(Project, pid)
            st = await s.get(ProjectStep, step_id)
            if p is None or st is None:
                return False
            st.execution_id = result.get("execution_id") if isinstance(result, dict) else None
            flow = get_flow(p.flow_key)
            d = step_def(flow, st.step_key) or {}
            if err:
                return await self._block(s, p, st, err)
            structured, passed = None, True
            if d.get("output"):
                data = schema.extract_json(output)
                errs = ["the answer was not a JSON object"] if data is None else schema.validate(data, d["output"])
                count = await self._expected_count(s, p, d, st)
                if data is not None and not errs and count:
                    got = len(data.get(d["count"]["field"]) or [])
                    if got != count:
                        errs.append(f"{d['count']['field']} has {got} items but the project needs {count}")
                if errs:
                    attempts = int((st.result_json or {}).get("_attempts", 0))
                    if attempts < 1:
                        # Ask the same agent once more, telling it exactly what was wrong.
                        st.status, st.started_at, st.ended_at = "queued", None, None
                        st.result_json = {**(st.result_json or {}), "_attempts": attempts + 1, "_format_errors": errs[:6]}
                        s.add(_sys_msg(pid, f"{st.tag}: the answer did not match the required structure "
                                            f"({'; '.join(errs[:3])}). Asking again.", "format", st.id))
                        await s.commit()
                        await notify("project", pid)
                        return True
                    return await self._block(s, p, st, "The answer did not match the required structure after "
                                                       "two tries: " + "; ".join(errs[:4]))
                structured = schema.apply_overrides(schema.coerce(data, d["output"]), d.get("override"))
                if d.get("verify_facts"):
                    structured = await self._verify_facts(s, p, st, structured)
                if d.get("verdict"):
                    verdict = str(structured.get("verdict", "pass")).lower().replace(" ", "_").replace("-", "_")
                    passed = verdict not in ("send_back", "sendback", "fail", "reject")
                    if not passed:
                        structured["reasons"] = structured.get("reasons") or "No reason given."
                structured, passed = await self._enforce_code_rules(s, p, d, structured, passed)
                return await self._complete(s, p, st, d, flow, structured,
                                            json.dumps(structured, ensure_ascii=False), passed=passed)
            if d.get("verdict"):
                m = VERDICT_RE.search(output)
                if m and m.group(1).upper().startswith("SEND"):
                    reasons = one_line(m.group(2), 300) or "No reason given."
                    structured, passed = {"verdict": "send_back", "reasons": reasons}, False
                else:
                    structured = {"verdict": "pass", "explicit": bool(m)}
                    if not m:
                        output += ("\n\n(No explicit verdict was given, so this check is recorded as a pass. "
                                   "The human gates still review the work.)")
                structured, passed = await self._enforce_code_rules(s, p, d, structured, passed)
                code = (structured or {}).get("code_check") or {}
                if code.get("findings"):
                    output += "\n\nCode rules found: " + "; ".join(code["findings"])
            return await self._complete(s, p, st, d, flow, structured, output, passed=passed)

    async def _verify_facts(self, s, p: Project, st: ProjectStep, structured: dict) -> dict:
        """Anvesh's facts are checked in code against the approved library (his own guarded tool)."""
        from agents.base import get_agent_module
        sources = await _approved_sources(s, p.client_id)
        library = {x["id"]: x for x in sources}
        try:
            res = get_agent_module(st.agent_id).verify_facts(facts=structured.get("facts") or [], library=library)
        except Exception as e:  # never let a checking problem mark anything verified
            log.exception("Fact verification failed for %s", p.id)
            res = {"facts": [{**(f if isinstance(f, dict) else {"fact": str(f)}), "verified": False,
                              "reason": f"verification failed: {e}"} for f in structured.get("facts") or []],
                   "verified": 0}
        out = dict(structured)
        out["facts"] = res["facts"]
        out["verified_count"] = res.get("verified", 0)
        out["sources_available"] = len(library)
        return out

    async def _enforce_code_rules(self, s, p: Project, d: dict, structured: dict | None,
                                  passed: bool) -> tuple[dict | None, bool]:
        """Safety rules decided in code: a rule finding forces a send-back, whatever the model said.

        The model can be stricter than the code (its own send-back stands), never looser.
        """
        cr = d.get("code_rules")
        if not cr:
            return structured, passed
        findings, n = await _safety_findings(s, p, cr.get("posts_from", "writing"), cr.get("evidence_from"),
                                             set(cr.get("rules") or []) or None)
        out = dict(structured or {})
        out["code_check"] = {"passed": not findings, "posts_checked": n,
                             "findings": [safety_rules.describe(f) for f in findings]}
        if not findings and not passed:
            # The model sent the work back. A reason about a rule the code checks exactly (the
            # disclaimer, empty fields, other clients) stands only if the code agrees.
            everything, _ = await _safety_findings(s, p, cr.get("posts_from", "writing"), cr.get("evidence_from"))
            kept, dropped = safety_rules.overrule(out.get("reasons"), everything, n)
            if dropped:
                issues = [i for i in (out.get("issues") or []) if not (isinstance(i, dict) and safety_rules.overrule(
                    i.get("problem"), everything, n)[1])]
                out["overruled"] = [f"{r} (the code verified this rule is met)" for r in dropped]
                out["issues"] = issues
                if not kept:
                    out["model_verdict"] = "send_back (overruled: the code verified every rule it named)"
                    out["verdict"], out["reasons"] = "pass", "The reviewer's only reasons were contradicted by the code check."
                    return out, True
                out["reasons"] = kept
        if not findings:
            return out, passed
        reasons = ["Code rule: " + safety_rules.describe(f) for f in findings]
        model = out.get("reasons")
        if not passed and model:
            reasons += [f"Reviewer: {x}" for x in (model if isinstance(model, list) else [model])]
        if passed:
            out["model_verdict"] = "pass (overruled by the code rules)"
        out["verdict"], out["reasons"] = "send_back", reasons
        return out, False

    async def _complete(self, s, p: Project, st: ProjectStep, d: dict, flow: dict,
                        structured: dict | None, raw_text: str, passed: bool) -> bool:
        """Record a finished step and apply send-back, block and approval rules."""
        pid = p.id
        st.ended_at = utcnow()
        rj = dict(structured or {})
        if (st.result_json or {}).get("_packages") is not None:
            rj["_packages"] = st.result_json["_packages"]
        rj["_passed"] = passed
        st.result_json = rj
        text = readable(raw_text)
        if d.get("note"):
            text = f"{d['note'].strip()}\n\n{text}"
        st.summary = one_line(text)
        s.add(ProjectMessage(project_id=pid, author_type="agent", agent_id=st.agent_id,
                             step_id=st.id, kind="result", text=text))
        try:
            refs = await registers.save(s, p, st, schema.public(structured))
        except Exception as e:  # a register problem must not lose the step's work
            log.exception("Register save failed for %s/%s", pid, st.step_key)
            refs = [{"table": "error", "id": f"not saved: {e}"[:120]}]
        if refs:
            st.result_json = {**rj, "_saved": refs}

        # Rework coordinator: escalate when the round limit is passed.
        if st.step_key == (flow.get("rework") or {}).get("key") and (structured or {}).get("status") == "escalate_to_human":
            return await self._block(s, p, st, (
                f"Round limit reached: the work was sent back {(structured or {}).get('round', '?') } times. "
                "A human must decide: Retry for another round, or Stop the project."))

        if not passed:
            fail_mode = d.get("on_fail", "send_back" if d.get("verdict") else "block")
            if structured and str(structured.get("verdict", "")).lower().replace(" ", "_") in ("send_back", "sendback", "fail"):
                r = structured.get("reasons")
                reasons = [str(x) for x in r] if isinstance(r, list) else [str(r)]
            else:
                reasons = _fail_reasons(structured or {})
            if fail_mode == "send_back" and d.get("send_back") and p.status not in ENDED_PROJECT_STATES:
                st.status = "completed"
                await self._send_back(s, p, st, d, flow, reasons)
                await s.commit()
                await notify("project", pid)
                return p.status == "running"
            return await self._block(s, p, st, f"{d.get('tag', st.tag)} did not pass: {'; '.join(reasons)}")

        appr = d.get("approval")
        if appr and p.status not in ENDED_PROJECT_STATES:
            req_id = new_approval_id()
            s.add(Approval(
                request_id=req_id, request_type="other", agent_id=st.agent_id,
                details={"kind": "project_step", "project_id": pid, "step_id": st.id,
                         "question": appr.get("question", "Can the team continue?"),
                         "why": " ".join((appr.get("why") or "").split())},
                requested_by=st.agent_id,
            ))
            st.approval_id = req_id
            st.status = "needs_attention"  # waiting for a human decision
            if st.step_key == "sweekriti":
                ref = await registers.open_approval(s, p, req_id, schema.public(structured))
                st.result_json = {**(st.result_json or {}),
                                  "_saved": list((st.result_json or {}).get("_saved") or []) + [ref]}
            await s.commit()
            await notify("project", pid)
            await notify("workforce")
            return False

        st.status = "completed"
        if st.step_key == "pipeline":
            await self._apply_plan(s, p, flow)
        keep_going = p.status == "running"
        await s.commit()
        await notify("project", pid)
        return keep_going

    async def _apply_plan(self, s, p: Project, flow: dict) -> None:
        """Pravartan's pipeline: each producer runs for exactly the packages Vitaran assigned to it."""
        plan = {x["step"]: x for x in await _production_plan(s, p.id, flow)}
        names = await _agent_names(s)
        lines = []
        for key in _production_keys(flow):
            d = step_def(flow, key)
            queued = (await s.execute(select(ProjectStep).where(
                ProjectStep.project_id == p.id, ProjectStep.step_key == key,
                ProjectStep.status == "queued"))).scalars().all()
            entry = plan.get(key)
            for qs in queued:
                if entry:
                    qs.result_json = {**(qs.result_json or {}), "_packages": entry["packages"]}
                else:
                    qs.status = "skipped"
                    qs.started_at = qs.ended_at = utcnow()
                    qs.summary = (f"Vitaran assigned no work packages to {names.get(d['agent'], d['agent'])}, "
                                  "so this step is skipped.")
                    s.add(_sys_msg(p.id, f"{names.get(d['agent'], d['agent'])} · {d['tag']}: skipped. {qs.summary}",
                                   "skipped", qs.id))
            if entry:
                lines.append(f"{entry['agent_name']} ({len(entry['packages'])} package(s))")
        s.add(_sys_msg(p.id, "Pravartan started the production pipeline from Vitaran's assignments: "
                             + (", then ".join(lines) if lines else "no producer has work") + ".", "pipeline"))

    async def _send_back(self, s, p: Project, st: ProjectStep, d: dict, flow: dict, reasons: list[str]) -> None:
        """Checker sent the work back: Punargathan opens a rework round, the producers run again, checks repeat."""
        sb = d["send_back"]
        rework_key = (flow.get("rework") or {}).get("key")
        done = (await s.execute(select(func.count()).select_from(ProjectStep).where(
            ProjectStep.project_id == p.id, ProjectStep.step_key == rework_key))).scalar() or 0
        note = f"{d.get('tag', st.tag)} sent the work back: {'; '.join(reasons)}"
        max_rounds = int((flow.get("defaults") or {}).get("max_rework_rounds", 3))
        if rework_key and done >= max_rounds:
            # Punargathan escalates to a human; no further automatic rounds.
            keys = [rework_key]
        else:
            keys = ([rework_key] if rework_key else []) + list(sb["to"]) + checks_between(flow, sb["recheck_from"], st.step_key)
        prefill = {k: {"revision_note": note} for k in sb["to"]}
        if rework_key:
            prefill[rework_key] = {"pending_reasons": reasons, "round": done + 1}
        await _insert_rounds(s, p.id, st.seq, keys, flow, None, prefill)
        s.add(_sys_msg(p.id, f"{note}. Punargathan opens rework round {done + 1}; "
                             f"{', '.join(sb['to'])} run again and the checks repeat.", "send_back", st.id))

    # -----------------------------------------------------------------------
    # recovery after a backend restart
    # -----------------------------------------------------------------------

    async def recover(self) -> None:
        async with async_session_maker() as s:
            rows = (await s.execute(
                select(ProjectStep, Project)
                .join(Project, Project.id == ProjectStep.project_id)
                .where(ProjectStep.status == "in_progress")
            )).all()
            resume: list[tuple[str, int, str]] = []
            for st, p in rows:
                ref = st.dispatch_ref
                if ref and ref != dispatcher.LOCAL_REF and await redis_alive():
                    resume.append((p.id, st.id, ref))
                    continue
                st.status = "needs_attention"
                st.error = ("Interrupted: the backend restarted while this step was running. "
                            "Press Retry to run it again.")
                st.ended_at = utcnow()
                if p.status == "running":
                    p.status = "needs_attention"
                s.add(_sys_msg(p.id, st.error, "error", st.id))
            await s.commit()
            running = (await s.execute(select(Project.id).where(Project.status == "running"))).scalars().all()
        resumed = set()
        for pid, sid, ref in resume:
            resumed.add(pid)
            self.kick(pid, resume_step_id=sid, resume_ref=ref)
        for pid in running:
            if pid not in resumed:
                self.kick(pid)


runner = ProjectRunner()


# ---------------------------------------------------------------------------
# actions (called by the API for a signed-in human)
# ---------------------------------------------------------------------------

async def readiness(flow_key: str | None = None) -> dict:
    flow = get_flow(flow_key)
    async with async_session_maker() as s:
        agents = {a.canonical_id: a for a in (await s.execute(select(Agent))).scalars().all()}
    steps, not_active, seen = [], [], set()
    for d in [step_def(flow, x["key"]) for x in flow["steps"]] + ([step_def(flow, flow["rework"]["key"])] if flow.get("rework") else []):
        a = agents.get(d["agent"])
        state = a.status if a else "not registered"
        runs = d.get("mode", "think") != "skip"
        active = a is not None and a.status in RUNNABLE_STATES
        steps.append({
            "key": d["key"], "block": d.get("block"), "agent_id": d["agent"],
            "agent_name": a.name if a else d["agent"], "responsibility": d["responsibility"],
            "tag": d["tag"], "mode": d.get("mode", "think"), "state": state, "active": active,
            "needs_approval": bool(d.get("approval")),
        })
        if runs and not active and d["agent"] not in seen:
            seen.add(d["agent"])
            not_active.append({"canonical_id": d["agent"], "name": a.name if a else d["agent"], "state": state})
    from config.settings import get_settings
    return {"flow_key": flow["key"], "flow_name": flow.get("name"), "steps": steps,
            "ready": not not_active, "not_active": not_active,
            "client_id": get_settings().default_tenant_id}


async def activate_needed(user: str) -> dict:
    """Run the existing activation gate for every agent the flow needs and activate the ones that pass.

    Uses the same gate and transition as the agent page; an agent that fails the gate stays inactive.
    """
    from backend.core.agent_runtime import LifecycleState, run_activation_gate, transition
    ready = await readiness()
    results = []
    for a in ready["not_active"]:
        cid = a["canonical_id"]
        async with async_session_maker() as s:
            gate = await run_activation_gate(s, cid)
        if not gate.passed:
            results.append({"canonical_id": cid, "name": a["name"], "activated": False,
                            "reason": "; ".join(gate.failures)})
            continue
        try:
            await transition(cid, LifecycleState.ACTIVE, performed_by=user,
                             reason="Activated for the project chain after passing the activation gate",
                             gate_result=gate)
            results.append({"canonical_id": cid, "name": a["name"], "activated": True})
        except Exception as e:
            results.append({"canonical_id": cid, "name": a["name"], "activated": False, "reason": str(e)})
    await notify("workforce")
    return {"results": results, "activated": sum(1 for r in results if r["activated"]),
            "failed": [r for r in results if not r["activated"]]}


async def start_project(pid: str, message: str | None, user: str) -> None:
    async with async_session_maker() as s:
        p = await _project(s, pid)
        if p.status != "draft":
            raise ProjectError(409, "This project has already been started.")
    ready = await readiness(p.flow_key)
    if not ready["ready"]:
        raise ProjectError(409, {
            "message": "Some agents this project needs are not deployed yet, so it was not started.",
            "not_active": ready["not_active"],
        })
    flow = get_flow(p.flow_key)
    async with async_session_maker() as s:
        # atomic: only one click can move draft -> running
        res = await s.execute(
            update(Project).where(Project.id == pid, Project.status == "draft")
            .values(status="running", started_at=utcnow())
        )
        if res.rowcount != 1:
            await s.rollback()
            raise ProjectError(409, "This project has already been started.")
        if message and message.strip():
            s.add(ProjectMessage(project_id=pid, author_type="human", author=user, kind="start",
                                 text=message.strip()))
        else:
            s.add(_sys_msg(pid, f"{user} started the project with no extra instructions. "
                                "The agents begin on their own.", "start"))
        for i, d in enumerate(flow["steps"], start=1):
            s.add(ProjectStep(project_id=pid, seq=i * 10, step_key=d["key"], agent_id=d["agent"],
                              responsibility=d["responsibility"], tag=d["tag"], round=1, status="queued"))
        await s.commit()
    await notify("project", pid)
    await notify("workforce")
    runner.kick(pid)


async def add_message(pid: str, text: str, user: str) -> None:
    text = (text or "").strip()
    if not text:
        raise ProjectError(400, "Type a message first.")
    async with async_session_maker() as s:
        p = await _project(s, pid)
        if p.status in ENDED_PROJECT_STATES:
            raise ProjectError(409, "This project has ended; start a new run to give new instructions.")
        if p.status == "draft":
            raise ProjectError(409, "Start the project first.")
        s.add(ProjectMessage(project_id=pid, author_type="human", author=user, kind="message", text=text))
        await s.commit()
    await notify("project", pid)


async def set_paused(pid: str, paused: bool, user: str) -> None:
    async with async_session_maker() as s:
        p = await _project(s, pid)
        if paused:
            if p.status != "running":
                raise ProjectError(409, f"Only a running project can be paused (it is {p.status}).")
            p.status = "paused"
            s.add(_sys_msg(pid, f"{user} paused the project. A step that is already running will finish; "
                                "no new step starts until it is resumed.", "paused"))
        else:
            if p.status != "paused":
                raise ProjectError(409, f"Only a paused project can be resumed (it is {p.status}).")
            p.status = "running"
            s.add(_sys_msg(pid, f"{user} resumed the project.", "resumed"))
        await s.commit()
    await notify("project", pid)
    if not paused:
        runner.kick(pid)


async def stop_project(pid: str, user: str) -> None:
    async with async_session_maker() as s:
        p = await _project(s, pid)
        if p.status in ENDED_PROJECT_STATES:
            raise ProjectError(409, f"This project is already {p.status}.")
        p.status = "stopped"
        p.ended_at = utcnow()
        await s.execute(update(ProjectStep).where(
            ProjectStep.project_id == pid, ProjectStep.status == "queued").values(status="skipped"))
        s.add(_sys_msg(pid, f"{user} stopped the project. Steps that had not started were skipped.", "stopped"))
        await s.commit()
    await notify("project", pid)
    await notify("workforce")


def _rerun_keys(d: dict, step_key: str) -> list[str]:
    appr = d.get("approval") or {}
    keys = list(appr.get("rerun") or [])
    return keys or [step_key]


async def retry_step(pid: str, step_id: int, user: str) -> None:
    async with async_session_maker() as s:
        p = await _project(s, pid)
        if p.status in ENDED_PROJECT_STATES:
            raise ProjectError(409, f"This project is {p.status}; use Run again instead.")
        st = await s.get(ProjectStep, step_id)
        if st is None or st.project_id != pid:
            raise ProjectError(404, "Step not found.")
        if st.status != "needs_attention":
            raise ProjectError(409, "Only a step that needs attention can be retried.")
        later = (await s.execute(select(ProjectStep.id).where(
            ProjectStep.project_id == pid, ProjectStep.step_key == st.step_key,
            ProjectStep.seq > st.seq))).first()
        if later:
            raise ProjectError(409, "This step was already retried.")
        flow = get_flow(p.flow_key)
        d = step_def(flow, st.step_key) or {}
        source, prefill = None, None
        if st.approval_id:
            appr = (await s.execute(select(Approval).where(
                Approval.request_id == st.approval_id))).scalars().first()
            if appr is not None and appr.decision is None:
                raise ProjectError(409, "This step is waiting for your decision.")
            source = st.approval_id
            keys = _rerun_keys(d, st.step_key)
        elif st.step_key == (flow.get("rework") or {}).get("key"):
            # round limit reached: a human asks for one more round
            prev = st.result_json or {}
            prefill = {st.step_key: {"pending_reasons": prev.get("reasons") or prev.get("pending_reasons") or [],
                                     "round": int(prev.get("round", 1)), "max_rounds_override": True}}
            keys = []
            # skip the coordinator; run the producers and checks again directly
            last_send = None
            for x in flow["steps"]:
                if x.get("send_back"):
                    last_send = x
            if last_send:
                sb = last_send["send_back"]
                keys = list(sb["to"]) + checks_between(flow, sb["recheck_from"], last_send["key"])
                prefill = {k: {"revision_note": "A human asked for another round after the round limit."} for k in sb["to"]}
        else:
            keys = [st.step_key]
        await _insert_rounds(s, pid, st.seq, keys, flow, source, prefill)
        st.error = (st.error or "") + (" " if st.error else "") + f"(Retried by {user}.)"
        p.status = "running"
        s.add(_sys_msg(pid, f"{user} pressed Retry. A new round starts.", "retry", st.id))
        await s.commit()
    await notify("project", pid)
    runner.kick(pid)


DECISIONS = ("approve", "reject", "approve_with_changes")


CLIENT_ROLES = ("client_approver",)


async def decide(pid: str, request_id: str, decision: str, note: str | None, user: str,
                 role: str | None = None, user_client: str | None = None) -> dict:
    """Record a human decision on a gate.

    A gate with `signoff` parties (Gate 2) needs each party to approve: a qualified reviewer AND
    an authorised contact of the project's own client. One person cannot sign for two parties.
    A rejection or "approve with changes" from any party decides at once. Gates without
    sign-off parties are decided by the internal team (never by a client contact).
    """
    if decision not in DECISIONS:
        raise ProjectError(400, f"Decision must be one of {', '.join(DECISIONS)}.")
    note = (note or "").strip() or None
    if decision == "approve_with_changes" and not note:
        raise ProjectError(400, "Write your changes before choosing Approve with changes.")

    async with async_session_maker() as s:
        p = await _project(s, pid)
        st = (await s.execute(select(ProjectStep).where(
            ProjectStep.project_id == pid, ProjectStep.approval_id == request_id))).scalars().first()
        if st is None:
            raise ProjectError(404, "Approval request not found for this project.")
        now = utcnow()
        gate = (step_def(get_flow(p.flow_key), st.step_key) or {}).get("approval") or {}
        parties = gate.get("signoff") or []
        party = None
        if parties:
            party = next((x for x in parties if role in (x.get("roles") or [])), None)
            if party is None:
                raise ProjectError(403, "This gate needs " + " and ".join(x["label"] for x in parties) +
                                   f" to sign off; your role ({role or 'unknown'}) cannot sign it.")
            if party.get("client") and user_client != p.client_id:
                raise ProjectError(403, "You can only sign off content for your own client.")
            appr = (await s.execute(select(Approval).where(Approval.request_id == request_id))).scalars().first()
            if appr is not None and appr.decision is not None:
                raise ProjectError(409, {"message": "This request was already decided.",
                                         "decision": appr.decision, "decided_by": appr.decided_by})
            prior = (await s.execute(select(ApprovalSignoff).where(
                ApprovalSignoff.request_id == request_id))).scalars().all()
            for r in prior:
                if r.party == party["party"]:
                    raise ProjectError(409, f"{party['label']} has already signed ({r.decided_by}).")
                if r.decided_by == user:
                    raise ProjectError(409, "One person cannot sign for two parties.")
            s.add(ApprovalSignoff(request_id=request_id, project_id=pid, party=party["party"], decision=decision,
                                  note=note, decided_by=user, role=role, decided_at=now))
            signed_by = [{"party": r.party, "by": r.decided_by} for r in prior] + [{"party": party["party"], "by": user}]
            if decision == "approve":
                signed = {r.party for r in prior} | {party["party"]}
                missing = [x["label"] for x in parties if x["party"] not in signed]
                if missing:
                    s.add(ProjectMessage(project_id=pid, author_type="human", author=user, kind="decision",
                                         step_id=st.id, text=f"{party['label']} approved" + (f": {note}" if note else ".")
                                         + " Waiting for " + " and ".join(missing) + "."))
                    await s.commit()
                    await notify("project", pid)
                    return {"request_id": request_id, "decision": "approve", "note": note, "decided_by": user,
                            "party": party["party"], "waiting_for": missing}
        elif role in CLIENT_ROLES:
            raise ProjectError(403, "This decision belongs to the internal team.")
        # Record the decision exactly once (double clicks / two tabs are ignored).
        res = await s.execute(
            update(Approval)
            .where(Approval.request_id == request_id, Approval.decision.is_(None))
            .values(decision="reject" if decision == "reject" else "approve",
                    decided_by=user, decided_at=now, note=note)
        )
        if res.rowcount != 1:
            await s.rollback()
            existing = (await s.execute(select(ApprovalDecision).where(
                ApprovalDecision.request_id == request_id))).scalars().first()
            raise ProjectError(409, {
                "message": "This request was already decided.",
                "decision": existing.decision if existing else None,
                "decided_by": existing.decided_by if existing else None,
            })
        s.add(ApprovalDecision(request_id=request_id, project_id=pid, decision=decision, note=note,
                               decided_by=user, decided_at=now,
                               details={"step_id": st.id, "agent_id": st.agent_id,
                                        **({"party": party["party"], "signed_by": signed_by} if party else {})}))
        label = {"approve": "approved", "reject": "rejected",
                 "approve_with_changes": "approved with changes"}[decision]
        s.add(ProjectMessage(project_id=pid, author_type="human", author=user, kind="decision",
                             step_id=st.id, text=f"{label.capitalize()}" + (f": {note}" if note else ".")))
        flow = get_flow(p.flow_key)
        d = step_def(flow, st.step_key) or {}
        ended = p.status in ENDED_PROJECT_STATES
        try:
            await registers.record_decision(s, p, request_id, decision)
        except Exception:
            log.exception("Could not record the decision in approval_workflows")
        if decision == "approve":
            st.status = "completed"
        elif decision == "approve_with_changes":
            st.status = "completed"
            if not ended:
                await _insert_rounds(s, pid, st.seq, _rerun_keys(d, st.step_key), flow, request_id)
        else:
            st.status = "needs_attention"
            st.error = f"Rejected by {user}" + (f": {note}" if note else ".")
            if not ended:
                p.status = "needs_attention"
        await s.commit()
        agent_id, tenant = st.agent_id, p.client_id
        status_after = p.status

    # Inform the asking agent over the existing bus (durable log first).
    try:
        await bus.publish(BusEnvelope(
            event_type="approval.decision", source_agent="human", target_agent=agent_id,
            payload={"request_id": request_id, "project_id": pid, "decision": decision,
                     "note": note, "decided_by": user},
            tenant_id=tenant, workflow_id=pid,
        ))
    except Exception:
        log.exception("Could not publish approval decision to the bus")
    await notify("project", pid)
    await notify("workforce")
    if status_after == "running":
        runner.kick(pid)
    return {"request_id": request_id, "decision": decision, "note": note, "decided_by": user}
