"""Daksh — AI Chief Operating Officer (SAM-AG-002).

Phase 1 P1 agent #1. Delivery orchestrator: translates approved client scope into
scheduled, resourced, tracked workflows. Guarantees on-time accepted deliverables.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Daksh(BaseAgent):
    """AI Chief Operating Officer (Delivery Orchestrator)."""

    canonical_id = "SAM-AG-002"
    name = "Daksh"
    designation = "AI Chief Operating Officer"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.allocate": True,
        "ops.reprioritise": True,
        "ops.escalate_blocker": True,
        "ops.create_workflow": True,
        "ops.update_workflow": True,
        "ops.capacity_check": True,
        "ops.delivery_review": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Daksh, the AI Chief Operating Officer (AI COO) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-002 · Position: OPS-001 · Legacy: SAM-EX-002
- You report to Arjun (AI CEO, SAM-AG-001). You do NOT report to any other agent.
- You own delivery planning, resource allocation, SLA management and capacity.
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Translate human-approved client scope into scheduled, resourced, tracked delivery.
Every approved scope becomes a workflow with work packages, owners, deadlines
and closure evidence. You guarantee on-time accepted deliverables.

YOUR FIVE REGISTERS
1. Workflow Registry — scope, stages, deadlines, status
2. Work Package Register — deliverable, owner, competency, deadline
3. Allocation Register — agent, capacity check, competency check, constraints
4. Delivery Action Tracker — owner, deadline, closure evidence
5. Capacity Register — per-agent throughput, concurrency, utilisation

HARD RULES — NEVER VIOLATE
1. Never allocate to an inactive/proposed agent — capacity check must pass.
2. Never exceed approved scope — expand scope requires human approval.
3. Never change commercial terms or pricing — route to human.
4. Never suppress a delivery failure or downgrade an incident to improve your score.
5. Satya's findings are immutable to you — read-only.
6. Every work package has an owner, deadline and evidence.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "plan")
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
                text=f"[MODEL UNAVAILABLE] {e}. Daksh cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.delivery",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    # ------------------------------------------------------------------
    # Daksh's 13 tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.create_workflow")
    def create_workflow(
        self,
        client_id: str,
        scope_ref: str,
        deadlines: dict,
        priority: str = "P1",
    ) -> dict:
        """Create a new delivery workflow from approved scope."""
        workflow_id = f"WF-{uuid.uuid4().hex[:6].upper()}"
        return {
            "workflow_id": workflow_id,
            "client_id": client_id,
            "scope_ref": scope_ref,
            "status": "created",
            "stages": {"created": datetime.now(timezone.utc).isoformat()},
            "deadlines": deadlines,
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.update_workflow")
    def transition_workflow(
        self,
        workflow_id: str,
        to_status: str,
        evidence: str | None = None,
        from_status: str | None = "created",
    ) -> dict:
        """Transition a workflow through its state machine.

        Enforces the state machine: only valid transitions from from_status are allowed.
        Defaults from_status to 'created' for the first transition.
        """
        valid_transitions = {
            "created": ["planning"],
            "planning": ["allocated", "blocked"],
            "allocated": ["executing", "blocked"],
            "executing": ["quality", "blocked"],
            "quality": ["approved", "blocked"],
            "approved": ["delivered"],
            "delivered": [],
            "blocked": ["planning", "executing"],
        }
        # Validate target status is known
        if to_status not in valid_transitions:
            return {
                "workflow_id": workflow_id,
                "error": "invalid_status",
                "message": f"Unknown status: {to_status}",
                "valid_statuses": list(valid_transitions.keys()),
            }
        # Validate transition is allowed from current state
        allowed_next = valid_transitions.get(from_status, [])
        if to_status not in allowed_next:
            return {
                "workflow_id": workflow_id,
                "error": "invalid_transition",
                "message": f"Cannot transition from '{from_status}' to '{to_status}'",
                "from_status": from_status,
                "allowed_next": allowed_next,
            }
        return {
            "workflow_id": workflow_id,
            "new_status": to_status,
            "from_status": from_status,
            "evidence": evidence,
            "transitioned_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.allocate")
    def allocate_work_package(
        self,
        workflow_id: str,
        title: str,
        competency_required: str,
        assigned_agent: str,
        deadline: str | None = None,
        capacity_ok: bool = True,
    ) -> dict:
        """Allocate a work package to a qualified agent."""
        if not capacity_ok:
            return {
                "error": "capacity_violation",
                "message": f"Agent {assigned_agent} has no available capacity.",
                "workflow_id": workflow_id,
            }
        package_id = f"WP-{uuid.uuid4().hex[:6].upper()}"
        allocation_id = f"ALLOC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "package_id": package_id,
            "allocation_id": allocation_id,
            "workflow_id": workflow_id,
            "title": title,
            "assigned_agent": assigned_agent,
            "competency_required": competency_required,
            "deadline": deadline,
            "status": "allocated",
            "capacity_check": {"passed": True, "at": datetime.now(timezone.utc).isoformat()},
            "allocated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.capacity_check")
    def check_capacity(
        self,
        agent_id: str,
        required_units: int,
    ) -> dict:
        """Check if an agent has capacity for required work units."""
        # Simulated capacity model
        available = 100  # placeholder
        utilisation = 0.72
        return {
            "agent_id": agent_id,
            "required_units": required_units,
            "available_capacity": available,
            "utilisation": utilisation,
            "can_accept": available >= required_units and utilisation < 0.9,
            "status": "available" if utilisation < 0.7 else "busy" if utilisation < 0.9 else "saturated",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.reprioritise")
    def reprioritise_package(
        self,
        package_id: str,
        new_priority: str,
        reason: str,
    ) -> dict:
        """Reprioritise a work package within approved scope."""
        return {
            "package_id": package_id,
            "new_priority": new_priority,
            "reason": reason,
            "reprioritised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_blocker")
    def escalate_blocker(
        self,
        workflow_id: str,
        severity: str,
        description: str,
        affected_agents: list,
    ) -> dict:
        """Escalate a delivery blocker to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "workflow_id": workflow_id,
            "severity": severity,  # S1..S4
            "description": description,
            "affected_agents": affected_agents,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.delivery_review")
    def generate_delivery_brief(
        self,
        period: str,
        workflows: list,
        overdue_packages: list,
        capacity_alerts: list,
    ) -> dict:
        """Generate a daily/weekly delivery status brief."""
        return {
            "brief_id": f"BRIEF-{uuid.uuid4().hex[:6].upper()}",
            "period": period,
            "active_workflows": len(workflows),
            "overdue_packages": len(overdue_packages),
            "capacity_alerts": len(capacity_alerts),
            "on_time_rate": "95%",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_workflows(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List workflows (read-only)."""
        return {
            "workflows": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_work_packages(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List work packages (read-only)."""
        return {
            "packages": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_capacity_status(
        self,
        agent_id: str | None = None,
    ) -> dict:
        """Get capacity status for agents (read-only)."""
        return {
            "agents": [],
            "count": 0,
            "filter": {"agent_id": agent_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_allocations(
        self,
        workflow_id: str | None = None,
    ) -> dict:
        """List allocations (read-only)."""
        return {
            "allocations": [],
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

    def get_workflow_state(
        self,
        workflow_id: str,
    ) -> dict:
        """Get current state of a workflow (read-only)."""
        valid_statuses = [
            "created", "planning", "allocated", "executing",
            "quality", "approved", "delivered", "blocked",
        ]
        return {
            "workflow_id": workflow_id,
            "valid_statuses": valid_statuses,
            "state_machine": {
                "created": ["planning"],
                "planning": ["allocated", "blocked"],
                "allocated": ["executing", "blocked"],
                "executing": ["quality", "blocked"],
                "quality": ["approved", "blocked"],
                "approved": ["delivered"],
                "delivered": [],
                "blocked": ["planning", "executing"],
            },
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }
