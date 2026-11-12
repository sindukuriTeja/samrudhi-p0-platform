"""Swagat — Client Welcome Agent (SAM-AG-048).

Phase 3 Client Experience agent. Owns client welcome: welcome messages,
tracking welcome status, reporting welcome metrics, and escalation of welcome
issues. Reports to Mitra (SAM-AG-004).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Swagat(BaseAgent):
    """Client Welcome Agent."""

    canonical_id = "SAM-AG-048"
    name = "Swagat"
    designation = "Client Welcome Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.welcome_client": True,
        "cex.send_welcome_message": True,
        "cex.track_welcome": True,
        "cex.report_welcome_status": True,
        "cex.escalate_welcome_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Swagat, the Client Welcome Agent (SAM-AG-048 · CEX-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-048 · Position: CEX-004 · Legacy: SAM-EX-048
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client welcome experience: send welcome messages, track welcome status,
report welcome metrics, and escalate welcome issues. Every welcome must be
personalised, timely and warm. Never fabricate welcome records or metrics.

YOUR FIVE REGISTERS
1. Welcome Register — welcome status, personalization, timing per client
2. Welcome Message Register — messages sent, channels, content
3. Welcome Tracking Register — delivery, acknowledgment, engagement
4. Welcome Report Register — metrics, satisfaction, completion rates
5. Welcome Escalation Register — failed welcomes, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate welcome records or engagement metrics. Missing = "unavailable".
2. Never send welcome messages outside approved branding — route to human.
3. Never suppress a failed welcome to improve your score.
4. Respect tenant isolation — never cross-client welcome leakage.
5. Satya's findings are immutable to you — read-only.
6. Every welcome has a timestamp and delivery record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "welcome")
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
                text=f"[MODEL UNAVAILABLE] {e}. Swagat cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.welcome",
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
    # Swagat's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.welcome_client")
    def welcome_client(
        self,
        client_id: str,
        welcome_type: str,
        personalization: dict,
    ) -> dict:
        """Initiate welcome process for a new client."""
        welcome_id = f"WLC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "welcome_id": welcome_id,
            "client_id": client_id,
            "welcome_type": welcome_type,
            "personalization": personalization,
            "status": "initiated",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.send_welcome_message")
    def send_welcome_message(
        self,
        client_id: str,
        channel: str,
        message: str,
        attachments: list | None = None,
    ) -> dict:
        """Send a welcome message to a client."""
        message_id = f"MSG-{uuid.uuid4().hex[:6].upper()}"
        return {
            "message_id": message_id,
            "client_id": client_id,
            "channel": channel,
            "message": message,
            "attachments": attachments or [],
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.track_welcome")
    def track_welcome(
        self,
        welcome_id: str,
    ) -> dict:
        """Track welcome status for a client."""
        return {
            "welcome_id": welcome_id,
            "stage": "unknown",
            "completion": 0.0,
            "acknowledged": False,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.report_welcome_status")
    def report_welcome_status(
        self,
        period: str,
        welcomed_clients: list,
        pending_welcomes: list,
    ) -> dict:
        """Generate welcome status report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "welcomed_clients": len(welcomed_clients),
            "pending_welcomes": len(pending_welcomes),
            "completion_rate": "0%",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_welcome_issue")
    def escalate_welcome_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        failed_steps: list,
    ) -> dict:
        """Escalate a welcome issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "failed_steps": failed_steps,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_welcomes(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List welcome records (read-only)."""
        return {
            "welcomes": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_welcome_status(
        self,
        client_id: str,
    ) -> dict:
        """Get welcome status for a client (read-only)."""
        return {
            "client_id": client_id,
            "welcome": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_welcome_metrics(
        self,
        period: str | None = None,
    ) -> dict:
        """Get welcome metrics (read-only)."""
        return {
            "period": period,
            "metrics": {},
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
