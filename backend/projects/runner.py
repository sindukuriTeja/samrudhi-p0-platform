"""Project runner — a thin layer over the existing agents.

It walks the steps of a project flow (config/project_flows.yaml) in order and,
for each step:
  1. refuses to run an agent that is not Active (lifecycle state active/monitored)
  2. checks the step's permission with the existing authority guard
  3. dispatches the existing Celery task workers.tasks.run_agent_task
  4. stores a readable version of the result in the project conversation
  5. asks for a human decision (approvals table) when the flow says so

It contains no agent logic and never calls the model directly. Human
decisions are written only by the API endpoint for a signed-in user.
"""
import asyncio
import logging

from sqlalchemy import func, select, update

from backend.core.authority import AuthorityError, check_authority
from backend.core.message_bus import BusEnvelope, bus
from backend.database import async_session_maker
from backend.models import Agent, Approval
from backend.models.projects import ApprovalDecision, Project, ProjectMessage, ProjectStep
from backend.projects import dispatch as dispatcher
from backend.projects.common import (
    ENDED_PROJECT_STATES, RUNNABLE_STATES, new_approval_id, utcnow,
)
from backend.projects.events import notify, redis_alive
from backend.projects.flow import get_flow, revise_permission_for, step_def
from backend.projects.readable import one_line, readable

log = logging.getLogger("samrudhi.projects")

MODEL_UNAVAILABLE = "[MODEL UNAVAILABLE]"


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
        superseded = any(o.step_key == st.step_key for o in steps[i + 1:])
        if not superseded:
            issues.append(st)
    return issues


async def _insert_rounds(s, pid: str, after_seq: int, step_keys: list[str], flow: dict,
                         source_approval_id: str | None) -> list[ProjectStep]:
    """Insert new rounds of the given step keys right after after_seq. Earlier rounds are kept."""
    n = len(step_keys)
    await s.execute(
        update(ProjectStep)
        .where(ProjectStep.project_id == pid, ProjectStep.seq > after_seq)
        .values(seq=ProjectStep.seq + n)
    )
    created = []
    for i, key in enumerate(step_keys, start=1):
        d = step_def(flow, key)
        max_round = (await s.execute(
            select(func.max(ProjectStep.round)).where(
                ProjectStep.project_id == pid, ProjectStep.step_key == key)
        )).scalar() or 0
        st = ProjectStep(
            project_id=pid, seq=after_seq + i, step_key=key, agent_id=d["agent"],
            responsibility=d["responsibility"], tag=d["tag"], round=max_round + 1,
            status="queued", source_approval_id=source_approval_id,
        )
        s.add(st)
        created.append(st)
    return created


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
                if not await self._finish(pid, resume_step_id, result):
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

            agent = (await s.execute(
                select(Agent).where(Agent.canonical_id == step.agent_id))).scalars().first()
            d = step_def(flow, step.step_key) or {}
            agent_name = agent.name if agent else step.agent_id

            # Rule: an agent that is not Active must not run.
            if agent is None or agent.status not in RUNNABLE_STATES:
                state = agent.status if agent else "not registered"
                step.status = "needs_attention"
                step.error = (f"{agent_name} is not Active (state: {state}), so it was not run. "
                              f"Activate it on its agent page, then press Retry.")
                step.ended_at = utcnow()
                p.status = "needs_attention"
                s.add(_sys_msg(pid, step.error, "error", step.id))
                await s.commit()
                await notify("project", pid)
                return False

            # Rule: permissions are enforced in code by the authority guard.
            permission = d.get("permission")
            if step.source_approval_id:
                permission = revise_permission_for(flow, step.step_key) or permission
            try:
                if permission:
                    check_authority(step.agent_id, permission)
            except AuthorityError:
                step.status = "needs_attention"
                step.error = f"Blocked by the authority guard: {agent_name} may not perform '{permission}'."
                step.ended_at = utcnow()
                p.status = "needs_attention"
                s.add(_sys_msg(pid, step.error, "error", step.id))
                await s.commit()
                await notify("project", pid)
                return False

            task_text, context = await self._build_task(s, p, step, d)
            step.status = "in_progress"
            step.started_at = utcnow()
            step.ended_at = None
            step.error = None
            await s.commit()
            step_id = step.id
            args = [step.agent_id, task_text, p.client_id, p.id]
            kwargs = {"action": d.get("action"), "context": context}
        await notify("project", pid)

        async def _on_ref(ref: str) -> None:
            async with async_session_maker() as s2:
                st = await s2.get(ProjectStep, step_id)
                if st is not None:
                    st.dispatch_ref = ref
                    await s2.commit()

        result = await dispatcher.dispatch(args, kwargs, _on_ref)
        return await self._finish(pid, step_id, result)

    async def _build_task(self, s, p: Project, step: ProjectStep, d: dict) -> tuple[str, dict]:
        names = await _agent_names(s)
        humans = (await s.execute(
            select(ProjectMessage).where(
                ProjectMessage.project_id == p.id, ProjectMessage.author_type == "human",
                ProjectMessage.kind.in_(("start", "message")),
            ).order_by(ProjectMessage.created_at, ProjectMessage.id)
        )).scalars().all()
        done = (await s.execute(
            select(ProjectStep, ProjectMessage)
            .join(ProjectMessage, ProjectMessage.step_id == ProjectStep.id)
            .where(ProjectStep.project_id == p.id, ProjectMessage.author_type == "agent")
            .order_by(ProjectStep.seq)
        )).all()
        previous = [
            {
                "agent": names.get(st.agent_id, st.agent_id),
                "step": f"{st.tag} · round {st.round}" if st.round > 1 else st.tag,
                "result": (m.text[:700] + "…") if len(m.text) > 700 else m.text,
            }
            # Kept short: agents put this context into their prompt, and the local 7B model
            # must answer within the agent's own 120 s timeout.
            for st, m in done[-4:]
        ]
        note = None
        if step.source_approval_id:
            dec = (await s.execute(select(ApprovalDecision).where(
                ApprovalDecision.request_id == step.source_approval_id))).scalars().first()
            note = dec.note if dec else None

        parts = [d.get("instruction", "").strip(), f"Project: {p.name}."]
        if humans:
            parts.append("Instructions from the human team: " + " | ".join(h.text for h in humans))
        if note:
            parts.append(f"Revise the earlier work using this note from the human reviewer: {note}")
        context = {
            "project_id": p.id,
            "project": p.name,
            "client_id": p.client_id,
            "workflow_stage": d.get("stage"),
            "round": step.round,
            "human_instructions": [h.text for h in humans],
            "previous_work": previous,
        }
        if note:
            context["revision_note"] = note
        return "\n".join(x for x in parts if x), context

    async def _finish(self, pid: str, step_id: int, result: dict) -> bool:
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
            st.ended_at = utcnow()
            flow = get_flow(p.flow_key)
            d = step_def(flow, st.step_key) or {}

            if err:
                st.status = "needs_attention"
                st.error = err
                if p.status == "running":
                    p.status = "needs_attention"
                s.add(_sys_msg(pid, err, "error", st.id))
                await s.commit()
                await notify("project", pid)
                return False

            text = readable(output)
            st.summary = one_line(text)
            s.add(ProjectMessage(project_id=pid, author_type="agent", agent_id=st.agent_id,
                                 step_id=st.id, kind="result", text=text))

            appr = d.get("approval")
            if appr and p.status not in ENDED_PROJECT_STATES:
                req_id = new_approval_id()
                s.add(Approval(
                    request_id=req_id, request_type="other", agent_id=st.agent_id,
                    details={"kind": "project_step", "project_id": pid, "step_id": st.id,
                             "question": appr.get("question", "Can the team continue?")},
                    requested_by=st.agent_id,
                ))
                st.approval_id = req_id
                st.status = "needs_attention"  # waiting for a human decision
                await s.commit()
                await notify("project", pid)
                await notify("workforce")
                return False

            st.status = "completed"
            keep_going = p.status == "running"
            await s.commit()
        await notify("project", pid)
        return keep_going

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
                    # The task lives in the broker / result backend: wait for it again
                    # (wait_celery gives up if it never starts).
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
    for d in flow["steps"]:
        a = agents.get(d["agent"])
        state = a.status if a else "not registered"
        active = a is not None and a.status in RUNNABLE_STATES
        steps.append({
            "key": d["key"], "agent_id": d["agent"], "agent_name": a.name if a else d["agent"],
            "responsibility": d["responsibility"], "tag": d["tag"], "state": state, "active": active,
            "needs_approval": bool(d.get("approval")),
        })
        if not active and d["agent"] not in seen:
            seen.add(d["agent"])
            not_active.append({"canonical_id": d["agent"], "name": a.name if a else d["agent"], "state": state})
    from config.settings import get_settings
    return {"flow_key": flow["key"], "flow_name": flow.get("name"), "steps": steps,
            "ready": not not_active, "not_active": not_active,
            "client_id": get_settings().default_tenant_id}


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
        source = None
        if st.approval_id:
            appr = (await s.execute(select(Approval).where(
                Approval.request_id == st.approval_id))).scalars().first()
            if appr is not None and appr.decision is None:
                raise ProjectError(409, "This step is waiting for your decision.")
            source = st.approval_id
            keys = [k for k in ((d.get("approval") or {}).get("revise_step"), st.step_key) if k]
        else:
            keys = [st.step_key]
        await _insert_rounds(s, pid, st.seq, keys, flow, source)
        st.error = (st.error or "") + (" " if st.error else "") + f"(Retried by {user}.)"
        p.status = "running"
        s.add(_sys_msg(pid, f"{user} pressed Retry. A new round starts.", "retry", st.id))
        await s.commit()
    await notify("project", pid)
    runner.kick(pid)


DECISIONS = ("approve", "reject", "approve_with_changes")


async def decide(pid: str, request_id: str, decision: str, note: str | None, user: str) -> dict:
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
                               details={"step_id": st.id, "agent_id": st.agent_id}))
        label = {"approve": "approved", "reject": "rejected",
                 "approve_with_changes": "approved with changes"}[decision]
        s.add(ProjectMessage(project_id=pid, author_type="human", author=user, kind="decision",
                             step_id=st.id, text=f"{label.capitalize()}" + (f": {note}" if note else ".")))
        flow = get_flow(p.flow_key)
        d = step_def(flow, st.step_key) or {}
        ended = p.status in ENDED_PROJECT_STATES
        if decision == "approve":
            st.status = "completed"
        elif decision == "approve_with_changes":
            st.status = "completed"
            if not ended:
                keys = [k for k in ((d.get("approval") or {}).get("revise_step"), st.step_key) if k]
                await _insert_rounds(s, pid, st.seq, keys, flow, request_id)
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
