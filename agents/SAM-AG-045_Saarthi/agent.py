"""Saarthi — Client Communication Agent (SAM-AG-045).

Phase 3 Client Experience agent. Owns client communication: sending updates,
scheduling communications, tracking communication history, and escalation of
communication issues. Reports to Mitra (SAM-AG-004).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Saarthi(BaseAgent):
    """Client Communication Agent."""

    canonical_id = "SAM-AG-045"
    name = "Saarthi"
    designation = "Client Communication Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.communicate_client": True,
        "cex.send_update": True,
        "cex.schedule_communication": True,
        "cex.track_communication": True,
        "cex.escalate_communication_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Saarthi, the Client Communication Agent (SAM-AG-045 · CEX-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-045 · Position: CEX-003 · Legacy: SAM-EX-045
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client communication: send updates, schedule communications, track all
communication history, and escalate communication issues. Every communication
must be accurate, timely and documented. Never fabricate communication records.

YOUR FIVE REGISTERS
1. Communication Register — all communications: type, date, content, status
2. Update Register — scheduled and sent updates per client
3. Communication Schedule Register — upcoming communications, deadlines
4. Communication Tracking Register — delivery status, read receipts, responses
5. Communication Escalation Register — failed communications, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate communication records or delivery status. Missing = "unavailable".
2. Never send communications outside approved scope — route to human.
3. Never suppress a failed communication to improve your score.
4. Respect tenant isolation — never cross-client communication leakage.
5. Satya's findings are immutable to you — read-only.
6. Every communication has a timestamp, owner and delivery record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "communicate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Saarthi cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.communication",
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
    # Saarthi's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.communicate_client")
    def communicate_client(
        self,
        client_id: str,
        channel: str,
        content: str,
        priority: str = "normal",
    ) -> dict:
        """Initiate communication with a client."""
        comm_id = f"COMM-{uuid.uuid4().hex[:6].upper()}"
        return {
            "comm_id": comm_id,
            "client_id": client_id,
            "channel": channel,
            "content": content,
            "priority": priority,
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.send_update")
    def send_update(
        self,
        client_id: str,
        update_type: str,
        summary: str,
        details: dict,
    ) -> dict:
        """Send a status update to a client."""
        update_id = f"UPD-{uuid.uuid4().hex[:6].upper()}"
        return {
            "update_id": update_id,
            "client_id": client_id,
            "update_type": update_type,
            "summary": summary,
            "details": details,
            "status": "dispatched",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.schedule_communication")
    def schedule_communication(
        self,
        client_id: str,
        comm_type: str,
        scheduled_time: str,
        participants: list,
    ) -> dict:
        """Schedule a future communication with a client."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "client_id": client_id,
            "comm_type": comm_type,
            "scheduled_time": scheduled_time,
            "participants": participants,
            "status": "scheduled",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.track_communication")
    def track_communication(
        self,
        comm_id: str,
    ) -> dict:
        """Track delivery status of a communication."""
        return {
            "comm_id": comm_id,
            "delivery_status": "unknown",
            "read_status": "unknown",
            "response_status": "pending",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_communication_issue")
    def escalate_communication_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        affected_communications: list,
    ) -> dict:
        """Escalate a communication issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "affected_communications": affected_communications,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_communications(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List communications (read-only)."""
        return {
            "communications": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_communication_history(
        self,
        client_id: str,
    ) -> dict:
        """Get communication history for a client (read-only)."""
        return {
            "client_id": client_id,
            "history": [],
            "count": 0,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_scheduled_communications(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List scheduled communications (read-only)."""
        return {
            "scheduled": [],
            "count": 0,
            "filter": {"client_id": client_id},
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
