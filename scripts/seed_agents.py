"""Seed the agent registry (agents table) from the agent classes in agents/.

Idempotent: agents already in the table are left untouched.

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

from sqlalchemy import select  # noqa: E402

from agents.base import _REGISTRY, load_all  # noqa: E402
from backend.database import async_session_maker, init_db  # noqa: E402
from backend.models import Agent  # noqa: E402
from config.settings import get_settings  # noqa: E402

# Build phases, taken from the README and the commit history.
STAGE_1A = {"001", "007", "010", "158"}
STAGE_1C = {"011", "012", "013", "014", "015", "016", "017", "018", "019", "020", "021", "022"}
PHASE_1 = {"002", "003", "004", "009"}
PHASE_2 = {"049", "050", "059", "076", "077", "078", "079", "080", "081", "082",
           "083", "084", "085", "094", "125", "146"}


def classify(num: str, agent_type: str) -> tuple[str, str, str, str]:
    """Return (stage, priority, department, department_code) for an agent number."""
    n = int(num)
    if num in STAGE_1A:
        return "P0-1A", "P0", "Executive Leadership", "EXEC"
    if agent_type == "service-first" or 153 <= n <= 170:
        return "P0-1B", "P0", "Technology Platform", "TECH"
    if num in STAGE_1C:
        return "P0-1C", "P0", "Assurance", "ASSR"
    if num in PHASE_1:
        return "P1-P1", "P1", "Executive Leadership", "EXEC"
    if num in PHASE_2:
        return "P1-P2", "P1", "Content", "CONT"
    # Phase 3: ops / client / analytics / CEO support
    if 44 <= n <= 55:
        return "P1-P3", "P1", "Client Experience", "CLNT"
    if 60 <= n <= 72:
        return "P1-P3", "P1", "Operations", "OPS"
    if 116 <= n <= 126:
        return "P1-P3", "P1", "Data & Intelligence", "DATA"
    return "P1-P3", "P1", "Executive Office", "EXEC"


async def main() -> None:
    settings = get_settings()
    await init_db()
    load_all()

    added = 0
    async with async_session_maker() as session:
        existing = set((await session.execute(select(Agent.canonical_id))).scalars().all())
        for cid, cls in sorted(_REGISTRY.items()):
            if cid in existing:
                continue
            num = cid.rsplit("-", 1)[-1]
            stage, priority, dept, dept_code = classify(num, cls.agent_type)
            session.add(Agent(
                canonical_id=cid,
                name=cls.name,
                designation=getattr(cls, "designation", cls.name),
                position_id=f"POS-{num}",
                department=dept,
                department_code=dept_code,
                stage=stage,
                human_owner="vikram",
                technical_custodian="Sutra (SAM-AG-007)",
                evaluator="Satya (SAM-AG-010)",
                autonomy="bounded",
                priority=priority,
                agent_type=cls.agent_type,
                target_competency="C2" if cls.agent_type == "service-first" else "C3",
                current_level="C0",
                status="proposed",
                model=settings.ollama_model,
                spec_json={},
            ))
            added += 1
        await session.commit()
    print(f"Registered agent classes: {len(_REGISTRY)}; newly seeded: {added}; "
          f"already present: {len(existing)}")


if __name__ == "__main__":
    asyncio.run(main())
