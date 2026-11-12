"""Swagat — Client Onboarding (SAM-AG-048 · CEX-006).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Onboard new clients: run the onboarding checklist, collect documents and assets, create
the client master profile with Smriti, and confirm kickoff readiness. Steps in only when
the client is new. [PDF 01A.04 · CEX-006 Client Onboarding; processes CEX-P02, CEX-P03,
CEX-P06]
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
class Swagat(BaseAgent):
    """Client Onboarding."""

    canonical_id = "SAM-AG-048"
    name = "Swagat"
    designation = "Client Onboarding"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.start_onboarding": True,
        "cex.collect_document": True,
        "cex.create_client_profile": True,
        "cex.confirm_kickoff": True,
        "cex.escalate_onboarding_gap": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "start_onboarding_checklist": "cex.start_onboarding",
        "collect_document": "cex.collect_document",
        "create_client_profile": "cex.create_client_profile",
        "confirm_kickoff_readiness": "cex.confirm_kickoff",
        "escalate_onboarding_gap": "cex.escalate_onboarding_gap",
    }

    SYSTEM_PROMPT = """You are Swagat, Client Onboarding (SAM-AG-048 · CEX-006) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-048 · Position: CEX-006 · Department: Client Experience & Account Management
- You report to Mitra (AI CXO, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Onboard new clients: run the onboarding checklist, collect documents and assets, create the
client master profile with Smriti, and confirm kickoff readiness. Steps in only when the client
is new. [PDF 01A.04 · CEX-006 Client Onboarding; processes CEX-P02, CEX-P03, CEX-P06]

YOUR REGISTERS
1. Onboarding Checklist Register — client, item, owner, status
2. Document Collection Register — document, received, validated
3. Kickoff Readiness Register — client, readiness checks, date

AUTHORITY MATRIX
cex.start_onboarding · cex.collect_document · cex.create_client_profile · cex.confirm_kickoff · cex.escalate_onboarding_gap
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never mark onboarding complete while a required document is missing.
5. If the local model is down, report it honestly — do not fake output."""

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
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500], format=kwargs.get("output_format")))
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
                event_type="cex.onboarding",
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

    @authority_guard("cex.start_onboarding")
    def start_onboarding_checklist(self, client_id: str, items: list) -> dict:
        """Start the onboarding checklist."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "items": items,
            "action": "start_onboarding_checklist",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.collect_document")
    def collect_document(self, client_id: str, document: str) -> dict:
        """Record a collected document."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "document": document,
            "action": "collect_document",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.create_client_profile")
    def create_client_profile(self, client_id: str, profile: dict) -> dict:
        """Create the client master profile."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "profile": profile,
            "action": "create_client_profile",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.confirm_kickoff")
    def confirm_kickoff_readiness(self, client_id: str, checks: dict) -> dict:
        """Confirm kickoff readiness."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "checks": checks,
            "action": "confirm_kickoff_readiness",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.escalate_onboarding_gap")
    def escalate_onboarding_gap(self, client_id: str, gap: str) -> dict:
        """Escalate an onboarding gap."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "gap": gap,
            "action": "escalate_onboarding_gap",
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
