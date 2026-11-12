"""Save each step's structured output to the agents' existing register tables.

Which register each step writes (architecture §8 and the P1 registers):
  kickoff         Arjun      -> initiatives
  actions         Samanvay   -> actions (one per owner)          close_actions -> closes them
  workflow        Daksh      -> workflow_instances (state machine: created -> planning -> allocated
                                 -> executing -> quality -> approved -> delivered; blocked on send-back)
  delivery_plan   Yojana     -> initiatives.milestones, workflow_instances.deadlines
  work_packages   Sankalan   -> work_packages
  schedule        Samay      -> work_packages.deadline
  assignments     Vitaran    -> work_packages.assigned_agent + allocations (with Kshamata's capacity check)
  direction       Disha      -> content_strategies
  calendar        Kalpana    -> content_calendars
  writing         Lekha      -> content_packages (one per post; later rounds update them)
  checks          Shuddhi, Pariksha, Gunvatta, Swasthya, Gopniya -> qa_reviews (one per content package)
  Gate 2          Sweekriti  -> approval_workflows (decision recorded when the human decides)
  client_update   Sandesh    -> client_communications
  publishing      Prakash    -> content_packages.status = scheduled, workflow delivered
  client_report   Prativedan -> reports
  final_brief     Arjun      -> briefs

IDs are derived from the project ID so later rounds update the same records instead of
creating duplicates. Returns a list of {"table", "id"} references for the step record.
"""
from datetime import datetime, timedelta

from sqlalchemy import select

from backend.models import (
    Action, Allocation, ApprovalWorkflow, Brief, ClientCommunication, ContentCalendar,
    ContentPackage, ContentStrategy, ExecutionLog, Initiative, QaReview, Report, WorkPackage,
    WorkflowInstance,
)
from backend.models.projects import ProjectStep
from backend.projects.common import utcnow

CHECK_KEYS = ("shuddhi", "pariksha", "gunvatta", "swasthya", "gopniya")

# Daksh's delivery workflow state machine (agents/SAM-AG-002 get_workflow_state; architecture §7.2)
VALID = {
    "created": ["planning"], "planning": ["allocated", "blocked"], "allocated": ["executing", "blocked"],
    "executing": ["quality", "blocked"], "quality": ["approved", "blocked"], "approved": ["delivered"],
    "delivered": [], "blocked": ["planning", "executing", "quality"],
}


def _path(src: str, dst: str) -> list[str]:
    """Shortest list of valid transitions from src to dst (empty if none)."""
    if src == dst:
        return []
    frontier, seen = [[src]], {src}
    while frontier:
        nxt = []
        for route in frontier:
            for s in VALID.get(route[-1], []):
                if s in seen:
                    continue
                if s == dst:
                    return route[1:] + [s]
                seen.add(s)
                nxt.append(route + [s])
        frontier = nxt
    return []


async def _workflow(s, pid: str) -> WorkflowInstance | None:
    return (await s.execute(select(WorkflowInstance).where(WorkflowInstance.workflow_id == pid))).scalars().first()


async def move_workflow(s, pid: str, to: str, reason: str) -> None:
    wf = await _workflow(s, pid)
    if wf is None or wf.status == to:
        return
    for state in _path(wf.status, to):
        wf.stages = list(wf.stages or []) + [{"from": wf.status, "to": state, "reason": reason,
                                              "at": utcnow().isoformat()}]
        wf.status = state


def _date(value):
    try:
        return datetime.fromisoformat(str(value)[:10])
    except Exception:
        return None


async def _packages(s, pid: str) -> list[ContentPackage]:
    rows = (await s.execute(select(ContentPackage).where(ContentPackage.package_id.like(f"CP-{pid}-%"))
                            .order_by(ContentPackage.package_id))).scalars().all()
    return list(rows)


async def save(s, p, st: ProjectStep, data: dict) -> list[dict]:
    """Write the step's structured output to its register(s). Unknown steps write nothing."""
    pid, key, now = p.id, st.step_key, utcnow()
    refs: list[dict] = []

    if key == "kickoff":
        ini = (await s.execute(select(Initiative).where(Initiative.objective_ref == pid))).scalars().first()
        if ini is None:
            ini = Initiative(title=p.name[:200], objective_ref=pid, owner_agent="SAM-AG-001",
                             milestones=[], status="active")
            s.add(ini)
        refs.append({"table": "initiatives", "id": pid})

    elif key == "actions":
        for owner in data.get("owners") or []:
            s.add(Action(owner=str(owner)[:100], task=f"[{pid}] Deliver your part of: {p.name}", status="open"))
        refs.append({"table": "actions", "id": f"{len(data.get('owners') or [])} open"})

    elif key == "close_actions":
        rows = (await s.execute(select(Action).where(Action.task.like(f"[{pid}]%"),
                                                     Action.status == "open"))).scalars().all()
        for a in rows:
            a.status, a.closure_evidence = "closed", f"Project {pid} completed; see final brief."
        refs.append({"table": "actions", "id": f"{len(rows)} closed"})

    elif key == "workflow":
        wf = await _workflow(s, pid)
        if wf is None:
            wf = WorkflowInstance(workflow_id=pid, client_id=p.client_id, scope_ref=pid, status="created",
                                  stages=[], deadlines={}, priority=str(data.get("priority", "P1"))[:10])
            s.add(wf)
            await s.flush()
        await move_workflow(s, pid, "planning", "Daksh created the delivery workflow")
        refs.append({"table": "workflow_instances", "id": pid})

    elif key == "delivery_plan":
        milestones = data.get("milestones") or []
        ini = (await s.execute(select(Initiative).where(Initiative.objective_ref == pid))).scalars().first()
        if ini is not None:
            ini.milestones = milestones
        wf = await _workflow(s, pid)
        if wf is not None:
            wf.deadlines = {str(m.get("name", i))[:80]: m.get("due") for i, m in enumerate(milestones) if isinstance(m, dict)}
        refs.append({"table": "initiatives", "id": f"{pid} milestones"})

    elif key == "work_packages":
        wf = await _workflow(s, pid)
        if wf is not None:
            for pk in data.get("work_packages") or []:
                exists = (await s.execute(select(WorkPackage).where(
                    WorkPackage.package_id == pk["package_id"]))).scalars().first()
                if exists is None:
                    s.add(WorkPackage(package_id=pk["package_id"], workflow_id=wf.id,
                                      title=f"{pk.get('type', 'package')} {pk.get('sequence', '')}".strip()[:200],
                                      competency_required=str(pk.get("type", ""))[:50], status="planned"))
            refs.append({"table": "work_packages", "id": f"{len(data.get('work_packages') or [])} packages"})

    elif key == "schedule":
        for pk in data.get("packages") or []:
            row = (await s.execute(select(WorkPackage).where(WorkPackage.package_id == pk.get("package_id")))).scalars().first()
            if row is not None:
                row.deadline = _date(pk.get("due_date"))
        refs.append({"table": "work_packages", "id": "deadlines set"})

    elif key == "assignments":
        cap = (await s.execute(select(ProjectStep).where(
            ProjectStep.project_id == pid, ProjectStep.step_key == "capacity")
            .order_by(ProjectStep.seq.desc()).limit(1))).scalars().first()
        n = 0
        for a in data.get("assignments") or []:
            row = (await s.execute(select(WorkPackage).where(WorkPackage.package_id == a.get("package_id")))).scalars().first()
            if row is None:
                continue
            assigned = a.get("assigned_to") or []
            row.assigned_agent = assigned[0] if assigned else None
            row.status = "allocated" if assigned else "unassigned"
            for agent in assigned:
                n += 1
                s.add(Allocation(allocation_id=f"AL-{a['package_id']}-{agent[-3:]}", work_package_id=row.id,
                                 agent_id=agent, competency_check={"package_type": a.get("type"), "qualified": True},
                                 capacity_check=(cap.result_json if cap else {}) or {}, constraints={},
                                 decision_ref=pid, status="allocated"))
        await move_workflow(s, pid, "allocated", "Vitaran assigned the work packages")
        refs.append({"table": "allocations", "id": f"{n} allocations"})

    elif key == "direction":
        sid = f"STR-{pid}-R{st.round}"
        s.add(ContentStrategy(strategy_id=sid, client_id=p.client_id, pillars=data.get("themes") or [],
                              themes=data.get("themes") or [], messaging=data.get("pieces") or [],
                              audience={"tone": data.get("tone")}, status="active"))
        refs.append({"table": "content_strategies", "id": sid})

    elif key == "calendar":
        cid = f"CAL-{pid}-R{st.round}"
        posts = data.get("posts") or []
        dates = [d for d in (_date(x.get("date")) for x in posts if isinstance(x, dict)) if d]
        s.add(ContentCalendar(calendar_id=cid, client_id=p.client_id, items=posts, status="draft",
                              period_start=min(dates) if dates else now,
                              period_end=max(dates) if dates else now + timedelta(days=30)))
        refs.append({"table": "content_calendars", "id": cid})

    elif key == "writing":
        cal = (await s.execute(select(ContentCalendar).where(ContentCalendar.calendar_id.like(f"CAL-{pid}-%"))
                               .order_by(ContentCalendar.created_at.desc()).limit(1))).scalars().first()
        existing = {c.package_id: c for c in await _packages(s, pid)}
        for i, post in enumerate(data.get("posts") or [], start=1):
            pkg_id = f"CP-{pid}-{i:02d}"
            title = str((post or {}).get("headline") or f"Post {i}")[:200]
            row = existing.get(pkg_id)
            if row is None and cal is not None:
                s.add(ContentPackage(package_id=pkg_id, calendar_id=cal.id, title=title, type="social_post",
                                     specialist="Lekha (SAM-AG-082)", status="draft"))
            elif row is not None:
                row.title, row.status = title, "revised"
        await move_workflow(s, pid, "executing", "Lekha is writing the content")
        refs.append({"table": "content_packages", "id": f"{len(data.get('posts') or [])} posts"})

    elif key in ("design_brief", "artwork"):
        for row in await _packages(s, pid):
            row.status = "in_production"
        refs.append({"table": "content_packages", "id": "in production"})

    elif key in CHECK_KEYS:
        rows = await _packages(s, pid)
        passed = (st.result_json or {}).get("_passed", True)
        for row in rows:
            s.add(QaReview(package_id=row.id, reviewer=st.agent_id, findings=data,
                           revisions={"round": st.round}, status="passed" if passed else "failed"))
            row.status = "in_qa"
        await move_workflow(s, pid, "quality", f"{st.tag} is checking the content")
        if not passed:
            await move_workflow(s, pid, "blocked", f"{st.tag} sent the work back")
            await move_workflow(s, pid, "executing", "Rework round")
        refs.append({"table": "qa_reviews", "id": f"{len(rows)} reviews"})

    elif key == "client_update":
        cid = f"COM-{pid}-R{st.round}"
        s.add(ClientCommunication(comm_id=cid, client_id=p.client_id, type="update",
                                  content=f"{data.get('subject', '')}\n\n{data.get('message', '')}".strip(),
                                  status="draft", owner="SAM-AG-051"))
        refs.append({"table": "client_communications", "id": cid})

    elif key == "publishing":
        for row in await _packages(s, pid):
            row.status = "scheduled"
        await move_workflow(s, pid, "delivered", "Prakash recorded the schedule")
        refs.append({"table": "content_packages", "id": "scheduled"})

    elif key == "client_report":
        rid = f"RPT-{pid}-R{st.round}"
        trace = (await s.execute(select(ExecutionLog.execution_id).where(ExecutionLog.workflow_id == pid))).scalars().all()
        s.add(Report(report_id=rid, client_id=p.client_id, type="client", content_ref=pid,
                     status="draft", source_trace=list(trace)))
        refs.append({"table": "reports", "id": rid})

    elif key == "final_brief":
        trace = (await s.execute(select(ExecutionLog.execution_id).where(ExecutionLog.workflow_id == pid))).scalars().all()
        s.add(Brief(brief_type="project", period=now, content={"project_id": pid, **data},
                    evidence_refs=list(trace), generated_by="SAM-AG-001"))
        refs.append({"table": "briefs", "id": pid})

    return refs


async def open_approval(s, p, request_id: str, evidence: dict) -> dict:
    """Gate 2: the approval request Sweekriti built becomes an approval workflow record."""
    s.add(ApprovalWorkflow(approval_id=request_id, client_id=p.client_id, item_ref=p.id,
                           approver="Qualified reviewer and client", status="pending", evidence=evidence or {}))
    return {"table": "approval_workflows", "id": request_id}


async def record_decision(s, p, request_id: str, decision: str) -> None:
    row = (await s.execute(select(ApprovalWorkflow).where(ApprovalWorkflow.approval_id == request_id))).scalars().first()
    if row is None:
        return
    row.status = {"approve": "approved", "reject": "rejected", "approve_with_changes": "changes"}[decision]
    if decision == "approve":
        for pkg in await _packages(s, p.id):
            pkg.status = "approved"
        await move_workflow(s, p.id, "approved", "Human approved the final content")
