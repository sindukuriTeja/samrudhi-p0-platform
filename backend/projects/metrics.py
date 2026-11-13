"""Measure a project from its own records (telemetry), in code.

Sources: execution_log (every agent run: time, tokens, true status), project_steps (rounds,
check results, timings), approvals + approval_decisions (human gate waits), Samay's schedule
(due dates) and the publishing step (delivery time). Nothing is estimated; a value that cannot
be measured yet is None.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from backend.models import Approval, ExecutionLog
from backend.models.projects import ApprovalDecision, ApprovalSignoff, Project, ProjectMessage, ProjectStep
from backend.projects.flow import get_flow, step_def

CHECK_KEYS_DEFAULT = ("shuddhi", "pariksha", "gunvatta", "swasthya", "gopniya")


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _seconds(a: datetime | None, b: datetime | None) -> float | None:
    a, b = _aware(a), _aware(b)
    return round((b - a).total_seconds(), 1) if a and b else None


def _ratio(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


async def project_metrics(s, pid: str) -> dict:
    p = await s.get(Project, pid)
    if p is None:
        return {}
    flow = get_flow(p.flow_key)
    steps = (await s.execute(select(ProjectStep).where(ProjectStep.project_id == pid)
                             .order_by(ProjectStep.seq))).scalars().all()
    execs = (await s.execute(select(ExecutionLog).where(ExecutionLog.workflow_id == pid))).scalars().all()

    # ---- agent runs (execution_log): model runs are everything that is not a code step
    tool_exec = {st.execution_id for st in steps
                 if st.execution_id and (step_def(flow, st.step_key) or {}).get("mode") == "tool"}
    model_runs = [e for e in execs if e.execution_id not in tool_exec]
    tool_runs = [e for e in execs if e.execution_id in tool_exec]

    def model_secs(e):
        t = (e.raw_result or {}).get("telemetry") if isinstance(e.raw_result, dict) else None
        if t and t.get("model_seconds") is not None:
            return float(t["model_seconds"])
        return float(e.latency_s or 0)

    failures = [e for e in model_runs if e.status == "failed"]
    format_retries = len((await s.execute(select(ProjectMessage.id).where(
        ProjectMessage.project_id == pid, ProjectMessage.kind == "format"))).scalars().all())

    # ---- checks, rework
    check_keys = set((flow.get("defaults") or {}).get("required_checks") or CHECK_KEYS_DEFAULT)
    check_runs = [st for st in steps if st.step_key in check_keys and st.status == "completed"]
    check_passed = [st for st in check_runs if (st.result_json or {}).get("_passed", True)]
    rework_key = (flow.get("rework") or {}).get("key", "rework")
    rework_rounds = len([st for st in steps if st.step_key == rework_key and st.status != "queued"])

    # ---- human gates
    gate_steps = [st for st in steps if st.approval_id]
    approvals = {a.request_id: a for a in (await s.execute(select(Approval).where(
        Approval.request_id.in_([st.approval_id for st in gate_steps] or ["-"])))).scalars().all()}
    decisions = (await s.execute(select(ApprovalDecision).where(ApprovalDecision.project_id == pid)
                                 .order_by(ApprovalDecision.decided_at))).scalars().all()
    by_req = {d.request_id: d for d in decisions}
    signoffs = (await s.execute(select(ApprovalSignoff).where(ApprovalSignoff.project_id == pid))).scalars().all()
    # every person's decision counts: final decisions plus the earlier sign-offs at multi-party gates
    extra_signoffs = [x for x in signoffs if not (by_req.get(x.request_id) and
                                                  by_req[x.request_id].decided_by == x.decided_by)]
    waits = []
    for st in gate_steps:
        a, d = approvals.get(st.approval_id), by_req.get(st.approval_id)
        if a is not None and d is not None:
            w = _seconds(a.requested_at, d.decided_at)
            if w is not None:
                waits.append(w)

    # ---- work packages: Samay's due dates vs. the publishing time
    def latest(key, completed=True):
        rows = [st for st in steps if st.step_key == key and (st.status == "completed" or not completed)]
        return rows[-1] if rows else None

    sched = latest("schedule")
    packages = ((sched.result_json or {}).get("packages") or []) if sched else []
    pub = latest("publishing")
    published = pub is not None and (pub.result_json or {}).get("status") == "scheduled"
    on_time = None
    if published and packages:
        done_day = _aware(pub.ended_at).date()
        due = []
        for x in packages:
            try:
                due.append(date.fromisoformat(str(x.get("due_date"))[:10]))
            except ValueError:
                pass
        on_time = _ratio(sum(1 for d_ in due if done_day <= d_), len(packages))

    # ---- research
    research = latest("research")
    facts = ((research.result_json or {}).get("facts") or []) if research else []
    verified = sum(1 for f in facts if isinstance(f, dict) and f.get("verified"))

    # ---- accepted deliverables: posts in the final copy, if a human approved Gate 2
    gate2 = [st for st in steps if st.step_key == "sweekriti" and st.approval_id]
    accepted = 0
    if gate2:
        d = by_req.get(gate2[-1].approval_id)
        if d is not None and d.decision in ("approve", "approve_with_changes"):
            writing = latest("writing")
            accepted = len(((writing.result_json or {}).get("posts") or [])) if writing else 0

    end = p.ended_at or datetime.now(timezone.utc)
    cycle = _seconds(p.started_at, end)
    return {
        "project_id": pid,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "cycle_time_hours": round(cycle / 3600.0, 2) if cycle is not None else None,
        "model_runs": len(model_runs),
        "tool_runs": len(tool_runs),
        "model_failures": len(failures),
        "model_failure_rate": _ratio(len(failures), len(model_runs)),
        "format_retries": format_retries,
        "tokens": int(sum(int(e.tokens_used or 0) for e in model_runs)),
        "prompt_tokens": int(sum(int(e.prompt_tokens or 0) for e in model_runs)),
        "response_tokens": int(sum(int(e.response_tokens or 0) for e in model_runs)),
        "model_seconds": round(sum(model_secs(e) for e in model_runs), 1),
        "check_runs": len(check_runs),
        "first_pass_rate": _ratio(len(check_passed), len(check_runs)),
        "rework_rounds": rework_rounds,
        "human_decisions": len(decisions) + len(extra_signoffs),
        "gate_wait_minutes": [round(w / 60.0, 1) for w in waits],
        "work_packages": len(packages),
        "on_time_rate": on_time,
        "facts": len(facts),
        "verified_facts": verified,
        "verified_fact_rate": _ratio(verified, len(facts)),
        "accepted_deliverables": accepted,
    }
