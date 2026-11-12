"""Read models for the Control Room (projects, history, workforce).

Everything returned here comes from the database; nothing is estimated.
"""
from sqlalchemy import func, select

from backend.core.llm import check_ollama_health
from backend.database import async_session_maker
from backend.models import Agent, Approval, ExecutionLog
from backend.models.projects import ApprovalDecision, Project, ProjectMessage, ProjectStep
from backend.projects.common import (
    ENDED_PROJECT_STATES, OPEN_PROJECT_STATES, RUNNABLE_STATES, iso, seconds_between, utcnow,
)
from backend.projects.events import redis_alive
from backend.projects.flow import BLOCKS, get_flow, step_def
from backend.projects.runner import ProjectError, open_issues


def _project_out(p: Project) -> dict:
    end = p.ended_at or (utcnow() if p.started_at and p.status not in ENDED_PROJECT_STATES else None)
    return {
        "id": p.id, "name": p.name, "client_id": p.client_id, "flow_key": p.flow_key,
        "status": p.status, "created_by": p.created_by, "created_at": iso(p.created_at),
        "started_at": iso(p.started_at), "ended_at": iso(p.ended_at),
        "duration_s": seconds_between(p.started_at, end), "rerun_of": p.rerun_of,
    }


async def _names(s) -> dict[str, dict]:
    rows = (await s.execute(select(Agent))).scalars().all()
    return {a.canonical_id: {"name": a.name, "designation": a.designation, "status": a.status} for a in rows}


def _step_out(st: ProjectStep, names: dict, superseded: bool, flow: dict | None = None) -> dict:
    d = (step_def(flow, st.step_key) if flow else None) or {}
    block = d.get("block")
    return {
        "block": block, "block_label": BLOCKS.get(block), "mode": d.get("mode", "think"),
        "result": {k: v for k, v in (st.result_json or {}).items() if not k.startswith("_")} or None,
        "passed": (st.result_json or {}).get("_passed"),
        "saved": (st.result_json or {}).get("_saved") or [],
        "packages": len((st.result_json or {}).get("_packages") or []) or None,
        "id": st.id, "seq": st.seq, "step_key": st.step_key, "agent_id": st.agent_id,
        "agent_name": names.get(st.agent_id, {}).get("name", st.agent_id),
        "responsibility": st.responsibility, "tag": st.tag, "round": st.round,
        "status": st.status, "started_at": iso(st.started_at), "ended_at": iso(st.ended_at),
        "elapsed_s": seconds_between(st.started_at, st.ended_at or (utcnow() if st.status == "in_progress" else None)),
        "summary": st.summary, "error": st.error, "execution_id": st.execution_id,
        "approval_id": st.approval_id, "source_approval_id": st.source_approval_id,
        "superseded": superseded,
    }


def _signoff(flow, st, rows) -> list[dict]:
    """Gate 2: each party that must approve, and who has signed so far."""
    if flow is None or st is None:
        return []
    from backend.projects.flow import step_def
    parties = ((step_def(flow, st.step_key) or {}).get("approval") or {}).get("signoff") or []
    out = []
    for x in parties:
        r = next((d for d in rows if d.party == x["party"]), None)
        out.append({"party": x["party"], "label": x["label"], "roles": x.get("roles") or [],
                    "signed_by": r.decided_by if r else None, "decision": r.decision if r else None})
    return out


async def project_state(pid: str) -> dict:
    async with async_session_maker() as s:
        p = await s.get(Project, pid)
        if p is None:
            raise ProjectError(404, f"Project {pid} not found")
        names = await _names(s)
        steps = (await s.execute(select(ProjectStep).where(
            ProjectStep.project_id == pid).order_by(ProjectStep.seq))).scalars().all()
        msgs = (await s.execute(select(ProjectMessage).where(
            ProjectMessage.project_id == pid).order_by(ProjectMessage.created_at, ProjectMessage.id))).scalars().all()
        appr_ids = [st.approval_id for st in steps if st.approval_id]
        approvals = (await s.execute(select(Approval).where(
            Approval.request_id.in_(appr_ids)))).scalars().all() if appr_ids else []
        decisions = {d.request_id: d for d in (await s.execute(select(ApprovalDecision).where(
            ApprovalDecision.request_id.in_(appr_ids)))).scalars().all()} if appr_ids else {}
        from backend.models.projects import ApprovalSignoff
        signoffs = (await s.execute(select(ApprovalSignoff).where(
            ApprovalSignoff.request_id.in_(appr_ids)))).scalars().all() if appr_ids else []

    try:
        flow = get_flow(p.flow_key)
    except KeyError:
        flow = None
    step_out = []
    for i, st in enumerate(steps):
        superseded = any(o.step_key == st.step_key for o in steps[i + 1:])
        step_out.append(_step_out(st, names, superseded, flow))
    by_step = {st.id: st for st in steps}
    appr_out = []
    for a in sorted(approvals, key=lambda a: a.requested_at or utcnow()):
        dec = decisions.get(a.request_id)
        st = next((x for x in steps if x.approval_id == a.request_id), None)
        appr_out.append({
            "request_id": a.request_id, "step_id": st.id if st else None,
            "agent_id": a.agent_id, "agent_name": names.get(a.agent_id, {}).get("name", a.agent_id),
            "question": (a.details or {}).get("question"), "why": (a.details or {}).get("why"),
            "requested_at": iso(a.requested_at),
            "decision": dec.decision if dec else a.decision, "note": dec.note if dec else a.note,
            "decided_by": dec.decided_by if dec else a.decided_by,
            "decided_at": iso(dec.decided_at if dec else a.decided_at),
            "pending": a.decision is None,
            "signoff": _signoff(flow, st, [d for d in signoffs if d.request_id == a.request_id]),
        })
    msg_out = []
    for m in msgs:
        st = by_step.get(m.step_id) if m.step_id else None
        msg_out.append({
            "id": m.id, "author_type": m.author_type, "author": m.author, "kind": m.kind,
            "agent_id": m.agent_id,
            "agent_name": names.get(m.agent_id, {}).get("name") if m.agent_id else None,
            "step_id": m.step_id, "step_tag": st.tag if st else None,
            "step_round": st.round if st else None, "step_status": st.status if st else None,
            "text": m.text, "created_at": iso(m.created_at),
        })
    visible = [x for x in step_out if x["status"] != "skipped"]
    counts = {
        "total": len(visible),
        "completed": sum(1 for x in visible if x["status"] == "completed"),
        "queued": sum(1 for x in visible if x["status"] == "queued"),
        "in_progress": sum(1 for x in visible if x["status"] == "in_progress"),
        "needs_attention": sum(1 for x in visible if x["status"] == "needs_attention" and not x["superseded"]),
    }
    return {
        "project": _project_out(p), "steps": step_out, "messages": msg_out,
        "approvals": appr_out, "counts": counts,
        "pending_approval": next((a for a in appr_out if a["pending"]), None),
    }


async def list_projects(statuses: list[str] | None = None) -> list[dict]:
    async with async_session_maker() as s:
        q = select(Project).order_by(Project.created_at.desc())
        if statuses:
            q = q.where(Project.status.in_(statuses))
        return [_project_out(p) for p in (await s.execute(q)).scalars().all()]


async def history(q: str | None = None) -> list[dict]:
    async with async_session_maker() as s:
        stmt = select(Project).where(Project.status.in_(ENDED_PROJECT_STATES)).order_by(
            Project.created_at.desc())
        if q:
            stmt = stmt.where(Project.name.ilike(f"%{q}%"))
        projects = (await s.execute(stmt)).scalars().all()
        used = dict((await s.execute(
            select(ProjectStep.project_id, func.count(func.distinct(ProjectStep.agent_id)))
            .where(ProjectStep.started_at.is_not(None))
            .group_by(ProjectStep.project_id))).all())
    out = []
    for p in projects:
        d = _project_out(p)
        d["agents_used"] = used.get(p.id, 0)
        out.append(d)
    return out


_DECISION_TEXT = {
    "approve": "approved", "reject": "rejected", "approve_with_changes": "approved with changes",
}


async def summary(pid: str) -> dict:
    state = await project_state(pid)
    p = state["project"]
    async with async_session_maker() as s:
        decisions = (await s.execute(select(ApprovalDecision).where(
            ApprovalDecision.project_id == pid).order_by(ApprovalDecision.decided_at))).scalars().all()
    flow = get_flow(p["flow_key"])
    timeline = []
    for m in state["messages"]:
        if m["author_type"] == "human" and m["kind"] in ("start", "message"):
            timeline.append({"type": "human", "at": m["created_at"],
                             "title": f"{m['author']} " + ("gave the task" if m["kind"] == "start" else "sent a message"),
                             "detail": m["text"]})
        elif m["author_type"] == "system" and m["kind"] in ("start", "paused", "resumed", "stopped", "retry", "completed"):
            timeline.append({"type": "system", "at": m["created_at"], "title": m["text"], "detail": None})
    for st in state["steps"]:
        if st["status"] in ("queued", "skipped"):
            continue
        name = f"{st['agent_name']} · {st['tag'].lower()}" + (f" · round {st['round']}" if st["round"] > 1 else "")
        timeline.append({
            "type": "step", "status": st["status"], "at": st["ended_at"] or st["started_at"],
            "title": name,
            "detail": st["error"] if st["status"] == "needs_attention" and st["error"] else st["summary"],
        })
    for d in decisions:
        timeline.append({"type": "decision", "decision": d.decision, "at": iso(d.decided_at),
                         "title": f"{d.decided_by} {_DECISION_TEXT.get(d.decision, d.decision)}",
                         "detail": d.note})
    timeline.sort(key=lambda x: x["at"] or "")

    deliverables = []
    for d in flow["steps"]:
        if not d.get("deliverable"):
            continue
        rounds = [st for st in state["steps"] if st["step_key"] == d["key"] and st["status"] == "completed"]
        if rounds:
            last = rounds[-1]
            deliverables.append({"name": d["deliverable"], "agent_name": last["agent_name"],
                                 "round": last["round"], "summary": last["summary"], "step_id": last["id"]})
    agents_used = len({st["agent_id"] for st in state["steps"] if st["started_at"]})
    return {
        "project": p,
        "tiles": {"duration_s": p["duration_s"], "agents_used": agents_used,
                  "human_approvals": len(decisions), "deliverables": len(deliverables)},
        "timeline": timeline, "deliverables": deliverables, "counts": state["counts"],
    }


# ---------------------------------------------------------------------------
# workforce
# ---------------------------------------------------------------------------

MONITORS = [
    ("SAM-AG-010", "Assurance", ("db",)),
    ("SAM-AG-158", "Records", ("db",)),
    ("SAM-AG-007", "Platform", ("db", "ollama")),
]


async def workforce() -> dict:
    db_ok = True
    try:
        async with async_session_maker() as s:
            agents = (await s.execute(select(Agent).order_by(Agent.canonical_id))).scalars().all()
            open_ids = select(Project.id).where(Project.status.in_(OPEN_PROJECT_STATES))
            running = set((await s.execute(select(ProjectStep.agent_id).where(
                ProjectStep.status == "in_progress", ProjectStep.project_id.in_(open_ids)))).scalars().all())
            awaiting = set((await s.execute(
                select(Approval.agent_id)
                .join(ProjectStep, ProjectStep.approval_id == Approval.request_id)
                .where(Approval.decision.is_(None), ProjectStep.project_id.in_(open_ids)))).scalars().all())
            attention: set[str] = set()
            for pid in (await s.execute(select(Project.id).where(
                    Project.status == "needs_attention"))).scalars().all():
                attention |= {st.agent_id for st in await open_issues(s, pid) if st.status == "needs_attention"}
            # last activity: latest project step per agent, else latest execution_log row
            step_rows = (await s.execute(
                select(ProjectStep, Project.name)
                .join(Project, Project.id == ProjectStep.project_id)
                .where(ProjectStep.started_at.is_not(None))
                .order_by(ProjectStep.started_at.desc()).limit(500))).all()
            exec_rows = (await s.execute(
                select(ExecutionLog.agent_id, ExecutionLog.task, ExecutionLog.status, ExecutionLog.ended_at,
                       ExecutionLog.started_at)
                .order_by(ExecutionLog.started_at.desc()).limit(500))).all()
    except Exception:
        db_ok = False
        agents = []

    if not db_ok:
        return {"available": False, "total": None, "counts": None, "agents": [],
                "monitoring": [], "health": await _health(False)}

    last: dict[str, dict] = {}
    for st, pname in step_rows:
        if st.agent_id in last:
            continue
        label = st.tag + (f" · round {st.round}" if st.round > 1 else "")
        verb = {"in_progress": "Working", "completed": "Done", "needs_attention": "Needs attention",
                "queued": "Queued", "skipped": "Skipped"}.get(st.status, st.status)
        last[st.agent_id] = {"text": f"{label} · {pname}", "status": verb,
                             "at": iso(st.ended_at or st.started_at)}
    for agent_id, task, status, ended, started in exec_rows:
        if agent_id in last:
            continue
        t = (task or "").strip().splitlines()[0] if task else "Run"
        last[agent_id] = {"text": (t[:80] + "…") if len(t) > 80 else t, "status": status,
                          "at": iso(ended or started)}

    counts = {"active": 0, "awaiting_approval": 0, "on_standby": 0, "not_deployed": 0, "needs_attention": 0}
    out = []
    for a in agents:
        deployed = a.status in RUNNABLE_STATES
        if not deployed:
            state = "not_deployed"
        elif a.canonical_id in running:
            state = "active"
        elif a.canonical_id in awaiting:
            state = "awaiting_approval"
        else:
            state = "on_standby"
        counts[state] += 1
        needs = a.canonical_id in attention or a.status == "restricted"
        if needs:
            counts["needs_attention"] += 1
        out.append({
            "canonical_id": a.canonical_id, "name": a.name, "designation": a.designation,
            "department": a.department, "stage": a.stage, "priority": a.priority,
            "agent_type": a.agent_type, "lifecycle_status": a.status, "state": state,
            "needs_attention": needs, "current_level": a.current_level,
            "target_competency": a.target_competency,
            "last_activity": last.get(a.canonical_id),
        })

    health = await _health(True)
    by_id = {a.canonical_id: a for a in agents}
    monitoring = []
    for cid, role, deps in MONITORS:
        a = by_id.get(cid)
        deployed = a is not None and a.status in RUNNABLE_STATES
        deps_ok = all(health[d] == "up" for d in deps)
        if not deps_ok:
            level, detail = "down", ", ".join(f"{d} {health[d]}" for d in deps if health[d] != "up")
        elif not deployed:
            level, detail = "idle", f"not deployed ({a.status if a else 'not registered'})"
        else:
            level, detail = "ok", a.status
        monitoring.append({"canonical_id": cid, "name": a.name if a else cid, "role": role,
                           "level": level, "detail": detail})
    return {"available": True, "total": len(agents), "counts": counts, "agents": out,
            "monitoring": monitoring, "health": health}


_ollama_cache: dict = {"at": 0.0, "value": None}


async def _health(db_ok: bool) -> dict:
    import time
    # Ollama's /api/tags can be slow while the model is generating; the sidebar
    # polls often, so reuse a result for up to 10 seconds.
    if _ollama_cache["value"] is None or time.monotonic() - _ollama_cache["at"] > 10:
        _ollama_cache.update(value=await check_ollama_health(), at=time.monotonic())
    o = _ollama_cache["value"]
    ollama = "up" if o.get("status") == "healthy" and o.get("configured_model_present", True) else (
        "model missing" if o.get("status") == "healthy" else "down")
    return {"api": "up", "db": "up" if db_ok else "down",
            "redis": "up" if await redis_alive() else "down", "ollama": ollama,
            "model": o.get("model")}
