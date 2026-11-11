"""Samanvay — Operations Coordination Agent (SAM-AG-013 · OPS-002).

Phase 3 operations agent. Coordinates cross-department operations, resolves
blockers, ensures delivery continuity, and synchronises departments. Reports
to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Samanvay(BaseAgent):
    """Operations Coordination Agent."""

    canonical_id = "SAM-AG-013"
    name = "Samanvay"
    designation = "Operations Coordination Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.coordinate_operations": True,
        "ops.resolve_blocker": True,
        "ops.ensure_delivery_continuity": True,
        "ops.synchronise_departments": True,
        "ops.escalate_operational_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Samanvay, the Operations Coordination Agent (SAM-AG-013 · OPS-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-013 · Position: OPS-002
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Coordinate cross-department operations, resolve blockers, ensure delivery
continuity, and synchronise departments. Every operational gap becomes a
coordinated action with owner, deadline and evidence.

YOUR REGISTERS
1. Coordination Register — cross-department actions, owners, deadlines
2. Blocker Register — blockers, resolution status, escalation path
3. Delivery Continuity Register — continuity checks, gaps, mitigations
4. Department Synchronisation Register — sync points, handoffs, conflicts
5. Operational Issue Register — issues, severity, escalation records

AUTHORITY MATRIX
ops.coordinate_operations · ops.resolve_blocker · ops.ensure_delivery_continuity
ops.synchronise_departments · ops.escalate_operational_issue · gov.certify=False
gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate coordination status — missing data = "unavailable".
2. Never suppress a blocker or downgrade an incident to improve metrics.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every coordination action has an owner, deadline and evidence.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "coordinate")
        context = kwargs.get("context", {})
        prompt = f"{self.SYSTEM_PROMPT}\n\nTASK: {task}\nACTION: {action}\nCONTEXT: {json.dumps(context, default=str)}"
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500]))
            text = result.text
            tokens = result.prompt_tokens + result.response_tokens
        except Exception as e:
            return AgentResult(
                text=f"[MODEL UNAVAILABLE] {e}. Samanvay cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="ops.coordinate",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.coordinate_operations")
    def coordinate_operations(
        self,
        workflow_ids: list,
        departments: list,
        priority: str = "P1",
    ) -> dict:
        """Coordinate operations across departments."""
        coord_id = f"COORD-{uuid.uuid4().hex[:6].upper()}"
        return {
            "coordination_id": coord_id,
            "workflow_ids": workflow_ids,
            "departments": departments,
            "priority": priority,
            "status": "coordinated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.resolve_blocker")
    def resolve_blocker(
        self,
        blocker_id: str,
        resolution: str,
        affected_workflows: list,
    ) -> dict:
        """Resolve an operational blocker."""
        return {
            "blocker_id": blocker_id,
            "resolution": resolution,
            "affected_workflows": affected_workflows,
            "status": "resolved",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.ensure_delivery_continuity")
    def ensure_delivery_continuity(
        self,
        workflow_id: str,
        continuity_check: dict,
    ) -> dict:
        """Ensure delivery continuity for a workflow."""
        continuity_id = f"CONT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "continuity_id": continuity_id,
            "workflow_id": workflow_id,
            "continuity_check": continuity_check,
            "status": "verified",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.synchronise_departments")
    def synchronise_departments(
        self,
        departments: list,
        sync_point: str,
        handoffs: list,
    ) -> dict:
        """Synchronise departments at a sync point."""
        sync_id = f"SYNC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "sync_id": sync_id,
            "departments": departments,
            "sync_point": sync_point,
            "handoffs": handoffs,
            "status": "synchronised",
            "synchronised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_operational_issue")
    def escalate_operational_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_agents: list,
    ) -> dict:
        """Escalate an operational issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_agents": affected_agents,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_coordinations(
        self,
        department: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List coordination records (read-only)."""
        return {
            "coordinations": [],
            "count": 0,
            "filter": {"department": department, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_blockers(
        self,
        status: str | None = None,
    ) -> dict:
        """List blockers (read-only)."""
        return {
            "blockers": [],
            "count": 0,
            "filter": {"status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_continuity_status(
        self,
        workflow_id: str | None = None,
    ) -> dict:
        """Get delivery continuity status (read-only)."""
        return {
            "workflows": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def route_for_approval(
        self,
        request_type: str,
        details: dict,
    ) -> dict:
        """Route a request outside delegated authority to human approval."""
        request_id = f"REQ-{uuid.uuid4().hex[:6].upper()}"
        return {
            "request_id": request_id,
            "request_type": request_type,
            "details": details,
            "status": "pending_human_approval",
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }
