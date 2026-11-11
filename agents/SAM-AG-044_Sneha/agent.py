"""Sneha — Client Onboarding Agent (SAM-AG-044).

Phase 3 Client Experience agent. Owns client onboarding: account setup,
requirements collection, service initialization, and onboarding issue escalation.
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
class Sneha(BaseAgent):
    """Client Onboarding Agent."""

    canonical_id = "SAM-AG-044"
    name = "Sneha"
    designation = "Client Onboarding Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.onboard_client": True,
        "cex.setup_account": True,
        "cex.collect_requirements": True,
        "cex.initialise_service": True,
        "cex.escalate_onboarding_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Sneha, the Client Onboarding Agent (SAM-AG-044 · CEX-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-044 · Position: CEX-002 · Legacy: SAM-EX-044
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client onboarding end-to-end: account setup, requirements collection,
service initialization, and escalation of onboarding issues. Every onboarding
must be accurate, complete and compliant. Never fabricate client data — missing
data = "unavailable".

YOUR FIVE REGISTERS
1. Onboarding Register — client profile, contract reference, status
2. Account Setup Register — credentials, access, configuration
3. Requirements Register — scope, deliverables, KPIs, compliance needs
4. Service Initiation Register — service activation, timelines, milestones
5. Onboarding Escalation Register — blocked items, escalations, resolutions

HARD RULES — NEVER VIOLATE
1. Never fabricate client requirements or service details. Missing = "unavailable".
2. Never change commercial terms or pricing — route to human.
3. Never suppress an onboarding blocker to improve your score.
4. Respect tenant isolation — never cross-client data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every onboarding step has a timestamp and status record.
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
                text=f"[MODEL UNAVAILABLE] {e}. Sneha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
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
    # Sneha's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.onboard_client")
    def onboard_client(
        self,
        client_id: str,
        contract_ref: str,
        brief: dict,
        contacts: dict,
    ) -> dict:
        """Onboard a new client."""
        onboarding_id = f"ONB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "onboarding_id": onboarding_id,
            "client_id": client_id,
            "contract_ref": contract_ref,
            "brief": brief,
            "contacts": contacts,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.setup_account")
    def setup_account(
        self,
        client_id: str,
        account_type: str,
        permissions: list,
    ) -> dict:
        """Set up client account and access."""
        account_id = f"ACC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "account_id": account_id,
            "client_id": client_id,
            "account_type": account_type,
            "permissions": permissions,
            "status": "provisioned",
            "setup_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.collect_requirements")
    def collect_requirements(
        self,
        client_id: str,
        scope: list,
        deliverables: list,
        kpis: dict,
    ) -> dict:
        """Collect client requirements and scope."""
        requirement_id = f"REQ-{uuid.uuid4().hex[:6].upper()}"
        return {
            "requirement_id": requirement_id,
            "client_id": client_id,
            "scope": scope,
            "deliverables": deliverables,
            "kpis": kpis,
            "status": "collected",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.initialise_service")
    def initialise_service(
        self,
        client_id: str,
        service_type: str,
        start_date: str,
        milestones: list,
    ) -> dict:
        """Initialize service for a client."""
        service_id = f"SRV-{uuid.uuid4().hex[:6].upper()}"
        return {
            "service_id": service_id,
            "client_id": client_id,
            "service_type": service_type,
            "start_date": start_date,
            "milestones": milestones,
            "status": "initialised",
            "initialised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_onboarding_issue")
    def escalate_onboarding_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        blocked_items: list,
    ) -> dict:
        """Escalate an onboarding issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "blocked_items": blocked_items,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_onboardings(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List onboarding records (read-only)."""
        return {
            "onboardings": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_account_status(
        self,
        client_id: str,
    ) -> dict:
        """Get account setup status (read-only)."""
        return {
            "client_id": client_id,
            "account": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_requirements(
        self,
        client_id: str,
    ) -> dict:
        """Get collected requirements (read-only)."""
        return {
            "client_id": client_id,
            "requirements": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_service_status(
        self,
        client_id: str,
    ) -> dict:
        """Get service initialization status (read-only)."""
        return {
            "client_id": client_id,
            "service": {},
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
