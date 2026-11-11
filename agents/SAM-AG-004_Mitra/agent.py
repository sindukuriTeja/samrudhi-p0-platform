"""Mitra — AI Chief Client Experience Officer (SAM-AG-004).

Phase 1 P1 agent #3. Owns client relationships: onboarding, communication,
approvals, feedback, retention. Coordinates client-facing interactions across
the delivery lifecycle.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Mitra(BaseAgent):
    """AI Chief Client Experience Officer (Client Experience)."""

    canonical_id = "SAM-AG-004"
    name = "Mitra"
    designation = "AI Chief Client Experience Officer"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.onboard_client": True,
        "cex.coordinate_communication": True,
        "cex.route_approval": True,
        "cex.collect_feedback": True,
        "cex.monitor_account": True,
        "cex.escalate_client": True,
        "cex.schedule_review": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Mitra, the AI Chief Client Experience Officer (AI CXO) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-004 · Position: CEX-001 · Legacy: SAM-EX-004
- You report to Arjun (AI CEO, SAM-AG-001). You do NOT report to any other agent.
- You own client experience, account performance and retention.
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client experience, account performance and retention. Coordinate client
communications, approvals and feedback across the delivery lifecycle. Every
client interaction must be accurate, timely and relationship-positive.

YOUR FIVE REGISTERS
1. Client Onboarding Register — brief, requirements, approval workflow, contacts
2. Client Communication Register — all communications: type, date, content, status
3. Approval Workflow Register — every approval: item, approver, status, deadline
4. Feedback Register — client feedback: source, category, routing, resolution
5. Account Health Register — satisfaction, retention signals, renewal readiness

HARD RULES — NEVER VIOLATE
1. Never change client pricing or commercial terms — route to human.
2. Never sign contracts or expand approved scope — route to human.
3. Never suppress a client complaint to improve your score.
4. Client satisfaction and retention are the primary measures of success.
5. Satya's findings are immutable to you — read-only.
6. Every client communication has an owner, timestamp and record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "onboard")
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
                text=f"[MODEL UNAVAILABLE] {e}. Mitra cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="cex.client",
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
    # Mitra's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.onboard_client")
    def onboard_client(
        self,
        client_id: str,
        contract_ref: str,
        brief: dict,
        approval_workflow: dict,
        contacts: dict,
    ) -> dict:
        """Onboard a new client."""
        onboarding_id = f"ONB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "onboarding_id": onboarding_id,
            "client_id": client_id,
            "contract_ref": contract_ref,
            "brief": brief,
            "approval_workflow": approval_workflow,
            "contacts": contacts,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.coordinate_communication")
    def create_communication(
        self,
        client_id: str,
        comm_type: str,
        content: str,
        owner: str,
    ) -> dict:
        """Create a client communication record."""
        comm_id = f"COMM-{uuid.uuid4().hex[:6].upper()}"
        return {
            "comm_id": comm_id,
            "client_id": client_id,
            "type": comm_type,
            "content": content,
            "owner": owner,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.route_approval")
    def route_for_approval(
        self,
        client_id: str,
        item_ref: str,
        approver: str,
        deadline: str | None = None,
    ) -> dict:
        """Route an item for client/human approval."""
        approval_id = f"APPR-{uuid.uuid4().hex[:6].upper()}"
        return {
            "approval_id": approval_id,
            "client_id": client_id,
            "item_ref": item_ref,
            "approver": approver,
            "deadline": deadline,
            "status": "pending",
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.collect_feedback")
    def record_feedback(
        self,
        client_id: str,
        source: str,
        category: str,
        routing: str,
    ) -> dict:
        """Record client feedback."""
        feedback_id = f"FB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "feedback_id": feedback_id,
            "client_id": client_id,
            "source": source,
            "category": category,
            "routing": routing,
            "status": "open",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.monitor_account")
    def update_account_health(
        self,
        client_id: str,
        satisfaction: float | None,
        retention_signals: dict,
        renewal_readiness: str,
        risks: dict,
    ) -> dict:
        """Update account health metrics."""
        return {
            "client_id": client_id,
            "satisfaction": satisfaction,
            "retention_signals": retention_signals,
            "renewal_readiness": renewal_readiness,
            "risks": risks,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_client")
    def escalate_client_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        affected_obligations: list,
    ) -> dict:
        """Escalate a client issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "affected_obligations": affected_obligations,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.schedule_review")
    def schedule_client_review(
        self,
        client_id: str,
        review_type: str,
        participants: list,
        agenda: str,
    ) -> dict:
        """Schedule a client review meeting."""
        review_id = f"REV-{uuid.uuid4().hex[:6].upper()}"
        return {
            "review_id": review_id,
            "client_id": client_id,
            "review_type": review_type,
            "participants": participants,
            "agenda": agenda,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_clients(
        self,
        status: str | None = None,
    ) -> dict:
        """List clients (read-only)."""
        return {
            "clients": [],
            "count": 0,
            "filter": {"status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_communications(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List client communications (read-only)."""
        return {
            "communications": [],
            "count": 0,
            "filter": {"client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_approvals(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List approval workflows (read-only)."""
        return {
            "approvals": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_feedback(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List feedback (read-only)."""
        return {
            "feedback": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_account_health(
        self,
        client_id: str,
    ) -> dict:
        """Get account health for a client (read-only)."""
        return {
            "client_id": client_id,
            "health": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def route_for_approval_external(
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
