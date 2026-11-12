"""Sweekriti — Client Appreciation Agent (SAM-AG-052).

Phase 3 Client Experience agent. Owns client appreciation: send appreciation
messages, track appreciation, report appreciation status, and escalation of
appreciation issues. Reports to Mitra (SAM-AG-004).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sweekriti(BaseAgent):
    """Client Appreciation Agent."""

    canonical_id = "SAM-AG-052"
    name = "Sweekriti"
    designation = "Client Appreciation Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.appreciate_client": True,
        "cex.send_appreciation": True,
        "cex.track_appreciation": True,
        "cex.report_appreciation": True,
        "cex.escalate_appreciation_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Sweekriti, the Client Appreciation Agent (SAM-AG-052 · CEX-006) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-052 · Position: CEX-006 · Legacy: SAM-EX-052
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client appreciation: send appreciation messages, track appreciation
engagement, report appreciation metrics, and escalate appreciation issues.
Every appreciation must be genuine, timely and personalised. Never fabricate
appreciation records or engagement data.

YOUR FIVE REGISTERS
1. Appreciation Register — appreciation events, occasions, status per client
2. Appreciation Message Register — messages sent, channels, content
3. Appreciation Tracking Register — delivery, acknowledgment, engagement
4. Appreciation Report Register — metrics, frequency, satisfaction impact
5. Appreciation Escalation Register — failed appreciations, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate appreciation records or engagement metrics. Missing = "unavailable".
2. Never send appreciation outside approved occasions — route to human.
3. Never suppress a failed appreciation to improve your score.
4. Respect tenant isolation — never cross-client appreciation leakage.
5. Satya's findings are immutable to you — read-only.
6. Every appreciation has a timestamp and delivery record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "appreciate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sweekriti cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.appreciation",
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
    # Sweekriti's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.appreciate_client")
    def appreciate_client(
        self,
        client_id: str,
        occasion: str,
        reason: str,
    ) -> dict:
        """Initiate client appreciation."""
        appreciation_id = f"APP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "appreciation_id": appreciation_id,
            "client_id": client_id,
            "occasion": occasion,
            "reason": reason,
            "status": "initiated",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.send_appreciation")
    def send_appreciation(
        self,
        client_id: str,
        channel: str,
        message: str,
        gift: str | None = None,
    ) -> dict:
        """Send an appreciation message to a client."""
        message_id = f"MSG-{uuid.uuid4().hex[:6].upper()}"
        return {
            "message_id": message_id,
            "client_id": client_id,
            "channel": channel,
            "message": message,
            "gift": gift,
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.track_appreciation")
    def track_appreciation(
        self,
        appreciation_id: str,
    ) -> dict:
        """Track appreciation status for a client."""
        return {
            "appreciation_id": appreciation_id,
            "delivery_status": "unknown",
            "acknowledged": False,
            "engagement": "unknown",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.report_appreciation")
    def report_appreciation(
        self,
        period: str,
        appreciated_clients: list,
        pending_appreciations: list,
    ) -> dict:
        """Generate appreciation status report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "appreciated_clients": len(appreciated_clients),
            "pending_appreciations": len(pending_appreciations),
            "engagement_rate": "0%",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_appreciation_issue")
    def escalate_appreciation_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        failed_appreciations: list,
    ) -> dict:
        """Escalate an appreciation issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "failed_appreciations": failed_appreciations,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_appreciations(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List appreciation records (read-only)."""
        return {
            "appreciations": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_appreciation_status(
        self,
        client_id: str,
    ) -> dict:
        """Get appreciation status for a client (read-only)."""
        return {
            "client_id": client_id,
            "appreciation": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_appreciation_metrics(
        self,
        period: str | None = None,
    ) -> dict:
        """Get appreciation metrics (read-only)."""
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
