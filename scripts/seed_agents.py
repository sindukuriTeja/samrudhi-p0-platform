"""Seed and reconcile the agent registry (agents table) with config/agent_registry.yaml.

config/agent_registry.yaml is the single source of truth for identity: canonical ID,
name, position, title, department, reporting line, stage, priority and agent type,
taken from the PDF canonical registry (Document 01C).

What this script does (idempotent, safe to run on every start):
  1. Inserts every registry agent that is missing, with status "proposed".
  2. Updates identity fields of existing rows to match the registry.
     It never changes lifecycle status, competency level or history.
  3. Removes rows that are not in the registry (or whose ID now belongs to a
     different agent) ONLY when they have no history at all (no lifecycle events,
     executions, project steps, approvals, findings or evaluations). Rows with
     history are reported and left alone for a human to decide.

Usage (from the project root):
    python -m scripts.seed_agents
Set DATABASE_URL first if you are not using PostgreSQL, e.g.
    DATABASE_URL=sqlite+aiosqlite:///./samrudhi_local.db
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from sqlalchemy import delete, func, select, update  # noqa: E402

from agents.base import _REGISTRY, load_all  # noqa: E402
from backend.database import async_session_maker, init_db  # noqa: E402
from backend.models import Agent, AgentSpec, AgentVersion, LifecycleEvent  # noqa: E402
from config.settings import get_settings  # noqa: E402

REGISTRY_PATH = ROOT / "config" / "agent_registry.yaml"
EXECUTIVE_TITLES = {  # keep the full executive designations used across the codebase
    "SAM-AG-001": "AI Chief Executive Officer",
    "SAM-AG-002": "AI Chief Operating Officer",
}


def load_registry() -> list[dict]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["agents"]


async def _has_history(s, cid: str) -> list[str]:
    """Names of tables that still reference this canonical ID."""
    from backend.models import Approval, Evaluation, ExecutionLog, Finding
    checks = [
        ("lifecycle_events", select(func.count()).select_from(LifecycleEvent).where(LifecycleEvent.canonical_id == cid)),
        ("execution_log", select(func.count()).select_from(ExecutionLog).where(ExecutionLog.agent_id == cid)),
        ("approvals", select(func.count()).select_from(Approval).where(Approval.agent_id == cid)),
        ("findings", select(func.count()).select_from(Finding).where(Finding.agent_id == cid)),
        ("evaluations", select(func.count()).select_from(Evaluation).where(Evaluation.agent_id == cid)),
    ]
    try:
        from backend.models.projects import ProjectStep
        checks.append(("project_steps", select(func.count()).select_from(ProjectStep).where(ProjectStep.agent_id == cid)))
    except Exception:
        pass
    used = []
    for table, q in checks:
        try:
            if (await s.execute(q)).scalar():
                used.append(table)
        except Exception:
            pass  # table not created yet
    return used


async def main() -> None:
    settings = get_settings()
    await init_db()
    load_all()
    registry = load_registry()
    by_id = {a["canonical_id"]: a for a in registry}

    added = updated = removed = 0
    kept_with_history: list[str] = []
    async with async_session_maker() as s:
        rows = {a.canonical_id: a for a in (await s.execute(select(Agent))).scalars().all()}

        # 3. remove rows that are not (or no longer) the registry's agent at that ID
        for cid, row in list(rows.items()):
            entry = by_id.get(cid)
            if entry is not None and entry["name"] == row.name:
                continue
            used = await _has_history(s, cid)
            if used:
                kept_with_history.append(f"{cid} {row.name} (referenced in {', '.join(used)})")
                continue
            for model in (AgentVersion, AgentSpec):
                await s.execute(delete(model).where(model.canonical_id == cid))
            await s.execute(update(Agent).where(Agent.reports_to_id == row.id).values(reports_to_id=None))
            await s.delete(row)
            del rows[cid]
            removed += 1
        await s.flush()

        # 1 + 2. insert or update identity fields
        for a in registry:
            cid = a["canonical_id"]
            cls = _REGISTRY.get(cid)
            fields = dict(
                name=a["name"],
                designation=EXECUTIVE_TITLES.get(cid) or (cls.designation if cls else a["title"]),
                position_id=a["position_id"],
                department=a["department"],
                department_code=a["department_code"],
                stage=a["stage"],
                priority=a["priority"],
                agent_type=a["agent_type"],
            )
            row = rows.get(cid)
            if row is None:
                row = Agent(
                    canonical_id=cid,
                    human_owner="vikram",
                    technical_custodian="Sutra (SAM-AG-007)",
                    evaluator="Satya (SAM-AG-010)",
                    autonomy="bounded",
                    target_competency="C2" if a["agent_type"] == "service-first" else "C3",
                    current_level="C0",
                    status="proposed",
                    model=settings.ollama_model,
                    spec_json={},
                    **fields,
                )
                s.add(row)
                rows[cid] = row
                added += 1
            elif any(getattr(row, k) != v for k, v in fields.items()):
                for k, v in fields.items():
                    setattr(row, k, v)
                updated += 1
        await s.flush()

        # reporting lines (agents.reports_to_id) from the registry
        for a in registry:
            head = rows.get(a["reports_to"])
            row = rows[a["canonical_id"]]
            want = head.id if head is not None else None
            if row.reports_to_id != want:
                row.reports_to_id = want
        await s.commit()

    print(f"Registry agents: {len(registry)}; added: {added}; updated: {updated}; removed: {removed}")
    for line in kept_with_history:
        print(f"  NOT removed (has history, decide manually): {line}")


if __name__ == "__main__":
    asyncio.run(main())
