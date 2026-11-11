"""Agent registry + lifecycle routes (Niyantrak's domain).

Endpoints for listing agents, viewing details, and running lifecycle transitions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.core.agent_runtime import (
    get_agent, list_agents, transition, run_activation_gate, GateResult,
    LifecycleState,
)
from backend.core.auth import get_current_user, require_role
from backend.models import Agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentOut(BaseModel):
    canonical_id: str
    name: str
    designation: str
    position_id: str
    department: str
    stage: str
    priority: str
    agent_type: str
    status: str
    current_level: str
    target_competency: str


class GateOut(BaseModel):
    agent_id: str
    passed: bool
    checks: dict
    failures: list
    checked_at: str


class TransitionRequest(BaseModel):
    to_state: str  # LifecycleState value
    reason: str | None = None


@router.get("", response_model=list[AgentOut])
async def agents_list(
    stage: str | None = None,
    status: str | None = None,
    priority: str | None = None,
):
    """List registered agents, filterable by stage/status/priority."""
    agents = await list_agents(stage=stage, status=status, priority=priority)
    return [
        AgentOut(
            canonical_id=a.canonical_id,
            name=a.name,
            designation=a.designation,
            position_id=a.position_id,
            department=a.department,
            stage=a.stage,
            priority=a.priority,
            agent_type=a.agent_type,
            status=a.status,
            current_level=a.current_level,
            target_competency=a.target_competency,
        )
        for a in agents
    ]


@router.get("/{canonical_id}", response_model=AgentOut)
async def agent_detail(canonical_id: str):
    """Get a single agent's registry record."""
    agent = await get_agent(canonical_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {canonical_id} not found",
        )
    return AgentOut(
        canonical_id=agent.canonical_id,
        name=agent.name,
        designation=agent.designation,
        position_id=agent.position_id,
        department=agent.department,
        stage=agent.stage,
        priority=agent.priority,
        agent_type=agent.agent_type,
        status=agent.status,
        current_level=agent.current_level,
        target_competency=agent.target_competency,
    )


@router.post("/{canonical_id}/transition")
async def agent_transition(
    canonical_id: str,
    req: TransitionRequest,
    user: dict = Depends(require_role("founder", "assurance_lead")),
):
    """Transition an agent's lifecycle state (human-gated).

    proposed→active requires a passing activation gate.
    """
    try:
        to_state = LifecycleState(req.to_state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state: {req.to_state}",
        )

    # If activating, run the gate first
    gate_result: GateResult | None = None
    agent = await get_agent(canonical_id)
    if agent and agent.status == LifecycleState.PROPOSED.value and to_state == LifecycleState.ACTIVE:
        async with __import__("backend.database", fromlist=["async_session_maker"]).async_session_maker() as s:
            gate_result = await run_activation_gate(s, canonical_id)
        if not gate_result.passed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Activation gate failed",
                headers={"X-Gate-Failures": "; ".join(gate_result.failures)},
            )

    try:
        await transition(
            canonical_id,
            to_state,
            performed_by=user["username"],
            reason=req.reason,
            gate_result=gate_result,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"canonical_id": canonical_id, "new_state": to_state.value, "success": True}


@router.post("/{canonical_id}/gate")
async def run_gate(canonical_id: str, user: dict = Depends(require_role("founder", "assurance_lead"))):
    """Run the activation gate for an agent without transitioning."""
    async with __import__("backend.database", fromlist=["async_session_maker"]).async_session_maker() as s:
        result = await run_activation_gate(s, canonical_id)
    if await get_agent(canonical_id) is None:
        raise HTTPException(status_code=404, detail=f"Agent {canonical_id} not found")
    return GateOut(
        agent_id=result.agent_id,
        passed=result.passed,
        checks=result.checks,
        failures=result.failures,
        checked_at=result.checked_at,
    )
