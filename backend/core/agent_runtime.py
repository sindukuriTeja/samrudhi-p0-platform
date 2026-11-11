"""Agent lifecycle state machine + activation gate (architecture section 9).

8-state lifecycle:
    proposed → registered → configured → evaluated → approved → active → monitored → restricted/retired

5-check deterministic activation gate (runs before proposed→active transition).
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models import Agent, LifecycleEvent, LifecycleState


class GateCheck(str, Enum):
    """The 5 deterministic checks before activation."""
    TOOL_PERMISSIONS = "tool_permissions_configured"
    COMPETENCY_TESTS = "competency_tests_passed"
    GOVERNANCE_TESTS = "governance_tests_passed"
    REPORTING_VALIDATED = "reporting_workflow_validated"
    ESCALATION_TESTED = "escalation_and_override_tested"


@dataclass
class GateResult:
    """Result of the activation gate."""
    agent_id: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# Each check is a callable that returns (passed: bool, message: str)
GateCheckFn = Callable[[AsyncSession, str], tuple[bool, str]]

# Registry of check implementations (populated by the platform / agents)
_GATE_CHECKS: dict[GateCheck, GateCheckFn] = {}


def register_gate_check(check: GateCheck, fn: GateCheckFn) -> None:
    """Register a function that implements a gate check."""
    _GATE_CHECKS[check] = fn


async def run_activation_gate(
    session: AsyncSession,
    canonical_id: str,
) -> GateResult:
    """Run all 5 deterministic checks for an agent.

    Returns GateResult; passed=True only if ALL checks pass.
    """
    checks = {}
    failures = []
    for check in GateCheck:
        fn = _GATE_CHECKS.get(check)
        if fn is None:
            # No implementation registered → treat as failed (deny by default)
            checks[check.value] = False
            failures.append(f"No implementation for gate check: {check.value}")
            continue
        try:
            passed, msg = await fn(session, canonical_id)
            checks[check.value] = passed
            if not passed:
                failures.append(f"{check.value}: {msg}")
        except Exception as e:
            checks[check.value] = False
            failures.append(f"{check.value}: exception {e}")

    return GateResult(
        agent_id=canonical_id,
        passed=len(failures) == 0,
        checks=checks,
        failures=failures,
    )


async def transition(
    canonical_id: str,
    to_state: LifecycleState,
    *,
    performed_by: str,
    reason: str | None = None,
    gate_result: GateResult | None = None,
) -> Agent:
    """Move an agent to a new lifecycle state and log the event.

    The transition proposed→active REQUIRES a passing gate result.
    Returns the updated Agent.
    """
    async with async_session_maker() as session:
        agent = (
            (await session.execute(
                select(Agent).where(Agent.canonical_id == canonical_id)
            ))
            .scalars()
            .first()
        )
        if agent is None:
            raise ValueError(f"Agent {canonical_id} not found in registry")

        from_state = LifecycleState(agent.status)
        if from_state == to_state:
            return agent  # no-op

        # Enforce proposed→active requires passing gate
        if from_state == LifecycleState.PROPOSED and to_state == LifecycleState.ACTIVE:
            if gate_result is None or not gate_result.passed:
                raise PermissionError(
                    "Activation (proposed→active) requires a passing activation gate. "
                    f"Gate result: {gate_result}"
                )

        agent.status = to_state.value
        session.add(agent)

        # Append-only lifecycle event
        event = LifecycleEvent(
            canonical_id=canonical_id,
            from_state=from_state.value,
            to_state=to_state.value,
            gate_results=gate_result.__dict__ if gate_result else {},
            performed_by=performed_by,
            reason=reason,
        )
        session.add(event)
        await session.commit()
        await session.refresh(agent)
        return agent


async def get_agent(canonical_id: str) -> Agent | None:
    async with async_session_maker() as session:
        return (
            (await session.execute(
                select(Agent).where(Agent.canonical_id == canonical_id)
            ))
            .scalars()
            .first()
        )


async def list_agents(
    *,
    stage: str | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> list[Agent]:
    async with async_session_maker() as session:
        stmt = select(Agent)
        if stage:
            stmt = stmt.where(Agent.stage == stage)
        if status:
            stmt = stmt.where(Agent.status == status)
        if priority:
            stmt = stmt.where(Agent.priority == priority)
        stmt = stmt.order_by(Agent.canonical_id)
        return (await session.execute(stmt)).scalars().all()
