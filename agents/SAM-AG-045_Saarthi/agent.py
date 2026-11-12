"""Saarthi — Client Operations Lead (SAM-AG-045 · CEX-003).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Run client operations: log and prioritise client requests, coordinate internal delivery
assignments, monitor request service levels and keep the client informed of progress.
[PDF 01A.04 · CEX-003 Client Operations & Coordination Lead; processes CEX-P09 to
CEX-P12]
Reports to Mitra (AI CXO, SAM-AG-004).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Saarthi(BaseAgent):
    """Client Operations Lead."""

    canonical_id = "SAM-AG-045"
    name = "Saarthi"
    designation = "Client Operations Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.log_client_request": True,
        "cex.prioritise_request": True,
        "cex.coordinate_delivery": True,
        "cex.track_request_sla": True,
        "cex.escalate_request": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "log_client_request": "cex.log_client_request",
        "prioritise_request": "cex.prioritise_request",
        "coordinate_delivery_assignment": "cex.coordinate_delivery",
        "track_request_sla": "cex.track_request_sla",
        "escalate_request": "cex.escalate_request",
    }

    SYSTEM_PROMPT = """You are Saarthi, Client Operations Lead (SAM-AG-045 · CEX-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-045 · Position: CEX-003 · Department: Client Experience & Account Management
- You report to Mitra (AI CXO, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Run client operations: log and prioritise client requests, coordinate internal delivery
assignments, monitor request service levels and keep the client informed of progress. [PDF
01A.04 · CEX-003 Client Operations & Coordination Lead; processes CEX-P09 to CEX-P12]

YOUR REGISTERS
1. Client Request Register — request, client, priority, owner, SLA, status
2. Delivery Coordination Register — request, assigned team, handoff, status
3. SLA Register — target, actual, breach, escalation

AUTHORITY MATRIX
cex.log_client_request · cex.prioritise_request · cex.coordinate_delivery · cex.track_request_sla · cex.escalate_request
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never promise delivery dates that operations has not confirmed.
5. If the local model is down, report it honestly — do not fake output."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Saarthi cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.operations",
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

    @authority_guard("cex.log_client_request")
    def log_client_request(self, client_id: str, request: str) -> dict:
        """Log a client request."""
        return {
            "record_id": f"SAA-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "request": request,
            "action": "log_client_request",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.prioritise_request")
    def prioritise_request(self, request_id: str, priority: str) -> dict:
        """Set a request's priority."""
        return {
            "record_id": f"SAA-{uuid.uuid4().hex[:6].upper()}",
            "request_id": request_id,
            "priority": priority,
            "action": "prioritise_request",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.coordinate_delivery")
    def coordinate_delivery_assignment(self, request_id: str, team: str) -> dict:
        """Hand a request to the delivery team."""
        return {
            "record_id": f"SAA-{uuid.uuid4().hex[:6].upper()}",
            "request_id": request_id,
            "team": team,
            "action": "coordinate_delivery_assignment",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.track_request_sla")
    def track_request_sla(self, request_id: str, sla_hours: int) -> dict:
        """Track a request against its SLA."""
        return {
            "record_id": f"SAA-{uuid.uuid4().hex[:6].upper()}",
            "request_id": request_id,
            "sla_hours": sla_hours,
            "action": "track_request_sla",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.escalate_request")
    def escalate_request(self, request_id: str, reason: str) -> dict:
        """Escalate a request."""
        return {
            "record_id": f"SAA-{uuid.uuid4().hex[:6].upper()}",
            "request_id": request_id,
            "reason": reason,
            "action": "escalate_request",
            "status": "recorded",
            "recorded_at": _now(),
        }

    # ------------------------------------------------------------------
    # Read-only and escalation
    # ------------------------------------------------------------------

    def list_records(self, register: str | None = None) -> dict:
        """List register records (read-only)."""
        return {
            "records": [],
            "count": 0,
            "filter": {"register": register},
            "queried_at": _now(),
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
            "routed_at": _now(),
        }
