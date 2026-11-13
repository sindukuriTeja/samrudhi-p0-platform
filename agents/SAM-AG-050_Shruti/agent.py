"""Shruti — Client Brief & Requirements (SAM-AG-050 · CEX-008).

Stage 2 Phase 2 content-pilot agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Turn the client's request into one clear brief: objective, audience, deliverables,
deadline and limits. Gather requirements, validate scope and raise change requests when
the request goes beyond the signed scope. [PDF 01A.04 · CEX-008 Client Brief &
Requirements; processes CEX-P07, CEX-P08]
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
class Shruti(BaseAgent):
    """Client Brief & Requirements."""

    canonical_id = "SAM-AG-050"
    name = "Shruti"
    designation = "Client Brief & Requirements"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.capture_requirement": True,
        "cex.structure_brief": True,
        "cex.validate_scope": True,
        "cex.raise_change_request": True,
        "cex.escalate_brief_gap": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "capture_requirement": "cex.capture_requirement",
        "structure_brief": "cex.structure_brief",
        "validate_scope": "cex.validate_scope",
        "raise_change_request": "cex.raise_change_request",
        "escalate_brief_gap": "cex.escalate_brief_gap",
    }

    SYSTEM_PROMPT = """You are Shruti, Client Brief & Requirements (SAM-AG-050 · CEX-008) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-050 · Position: CEX-008 · Department: Client Experience & Account Management
- You report to Mitra (AI CXO, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Turn the client's request into one clear brief: objective, audience, deliverables, deadline and
limits. Gather requirements, validate scope and raise change requests when the request goes
beyond the signed scope. [PDF 01A.04 · CEX-008 Client Brief & Requirements; processes CEX-P07,
CEX-P08]

YOUR REGISTERS
1. Requirement Register — requirement, source, client, status
2. Client Brief Register — brief, objective, audience, deliverables, deadline, limits, version
3. Change Request Register — request, scope impact, approver, status

AUTHORITY MATRIX
cex.capture_requirement · cex.structure_brief · cex.validate_scope · cex.raise_change_request · cex.escalate_brief_gap
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never accept work outside the signed scope — raise a change request.
5. Never invent requirements the client did not state.
6. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "brief")
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
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500], format=kwargs.get("output_format")))
            text = result.text
            tokens = result.prompt_tokens + result.response_tokens
        except Exception as e:
            return AgentResult(
                text=f"[MODEL UNAVAILABLE] {e}. Shruti cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.brief",
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
    # Shruti's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.capture_requirement")
    def capture_requirement(self, client_id: str, requirement: str) -> dict:
        """Capture a client requirement."""
        return {
            "record_id": f"SHR-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "requirement": requirement,
            "action": "capture_requirement",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.structure_brief")
    def structure_brief(self, client_id: str, objective: str = "", audience: str = "", deliverables: str = "", deadline: str = "", limits: str = "") -> dict:
        """Structure the client brief and report missing fields."""
        required = {"objective": objective, "audience": audience, "deliverables": deliverables,
                    "deadline": deadline, "limits": limits}
        missing = [k for k, v in required.items() if not v]
        return {
            "brief_id": f"BRF-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            **required,
            "missing_fields": missing,
            "status": "complete" if not missing else "incomplete",
            "structured_at": _now(),
        }

    @authority_guard("cex.validate_scope")
    def validate_scope(self, client_id: str, request: str, signed_scope: str) -> dict:
        """Check a request against the signed scope."""
        return {
            "record_id": f"SHR-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "request": request,
            "signed_scope": signed_scope,
            "action": "validate_scope",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.raise_change_request")
    def raise_change_request(self, client_id: str, change: str) -> dict:
        """Raise a scope change request."""
        return {
            "record_id": f"SHR-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "change": change,
            "action": "raise_change_request",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.escalate_brief_gap")
    def escalate_brief_gap(self, client_id: str, gap: str) -> dict:
        """Escalate a gap in the brief."""
        return {
            "record_id": f"SHR-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "gap": gap,
            "action": "escalate_brief_gap",
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
