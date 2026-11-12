"""Sandesh — Client Communication (SAM-AG-051).

Phase 3 Client Experience agent. Owns client messaging: compose messages,
schedule messages, track message delivery, and escalation of messaging issues.
Reports to Mitra (SAM-AG-004).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sandesh(BaseAgent):
    """Client Communication."""

    canonical_id = "SAM-AG-051"
    name = "Sandesh"
    designation = "Client Communication"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.message_client": True,
        "cex.compose_message": True,
        "cex.schedule_message": True,
        "cex.track_message": True,
        "cex.escalate_messaging_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Sandesh, Client Communication (SAM-AG-051 · CEX-009) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-051 · Position: CEX-009 · Legacy: SAM-EX-051
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client messaging: compose messages, schedule messages, track delivery,
and escalate messaging issues. Every message must be accurate, compliant and
well-timed. Never fabricate message content or delivery status.

YOUR FIVE REGISTERS
1. Message Register — all messages: content, channel, status per client
2. Composition Register — drafted messages, templates, variants
3. Message Schedule Register — scheduled sends, timing, frequency
4. Message Tracking Register — delivery, opens, clicks, responses
5. Messaging Escalation Register — failed messages, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate message content or delivery metrics. Missing = "unavailable".
2. Never send messages outside approved content — route to human.
3. Never suppress a failed message delivery to improve your score.
4. Respect tenant isolation — never cross-client message leakage.
5. Satya's findings are immutable to you — read-only.
6. Every message has a timestamp, channel and delivery record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "message")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sandesh cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.messaging",
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
    # Sandesh's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.message_client")
    def message_client(
        self,
        client_id: str,
        channel: str,
        content: str,
        urgency: str = "normal",
    ) -> dict:
        """Send a message to a client."""
        message_id = f"MSG-{uuid.uuid4().hex[:6].upper()}"
        return {
            "message_id": message_id,
            "client_id": client_id,
            "channel": channel,
            "content": content,
            "urgency": urgency,
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.compose_message")
    def compose_message(
        self,
        client_id: str,
        template: str,
        variables: dict,
        tone: str = "professional",
    ) -> dict:
        """Compose a message for a client."""
        draft_id = f"DRF-{uuid.uuid4().hex[:6].upper()}"
        return {
            "draft_id": draft_id,
            "client_id": client_id,
            "template": template,
            "variables": variables,
            "tone": tone,
            "status": "drafted",
            "drafted_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.schedule_message")
    def schedule_message(
        self,
        client_id: str,
        content: str,
        send_at: str,
        channel: str,
    ) -> dict:
        """Schedule a message for future delivery."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "client_id": client_id,
            "content": content,
            "send_at": send_at,
            "channel": channel,
            "status": "scheduled",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.track_message")
    def track_message(
        self,
        message_id: str,
    ) -> dict:
        """Track delivery status of a message."""
        return {
            "message_id": message_id,
            "delivery_status": "unknown",
            "read_at": None,
            "clicked": False,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_messaging_issue")
    def escalate_messaging_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        failed_messages: list,
    ) -> dict:
        """Escalate a messaging issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "failed_messages": failed_messages,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_messages(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List messages (read-only)."""
        return {
            "messages": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_message_status(
        self,
        message_id: str,
    ) -> dict:
        """Get message delivery status (read-only)."""
        return {
            "message_id": message_id,
            "status": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_scheduled_messages(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List scheduled messages (read-only)."""
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
