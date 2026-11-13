"""Sneha — Client Success Lead (SAM-AG-044 · CEX-002).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Own client relationships: account plans, stakeholder coordination, account reviews and
early signs of relationship risk. [PDF 01A.04 · CEX-002 Client Success & Relationship
Lead]
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
class Sneha(BaseAgent):
    """Client Success Lead."""

    canonical_id = "SAM-AG-044"
    name = "Sneha"
    designation = "Client Success Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.create_account_plan": True,
        "cex.record_stakeholder": True,
        "cex.schedule_account_review": True,
        "cex.flag_relationship_risk": True,
        "cex.escalate_client_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "create_account_plan": "cex.create_account_plan",
        "record_stakeholder": "cex.record_stakeholder",
        "schedule_account_review": "cex.schedule_account_review",
        "flag_relationship_risk": "cex.flag_relationship_risk",
        "escalate_client_issue": "cex.escalate_client_issue",
    }

    SYSTEM_PROMPT = """You are Sneha, Client Success Lead (SAM-AG-044 · CEX-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-044 · Position: CEX-002 · Department: Client Experience & Account Management
- You report to Mitra (AI CXO, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own client relationships: account plans, stakeholder coordination, account reviews and early
signs of relationship risk. [PDF 01A.04 · CEX-002 Client Success & Relationship Lead]

YOUR REGISTERS
1. Account Plan Register — client, objectives, stakeholders, review dates
2. Stakeholder Register — contacts, roles, communication preferences
3. Relationship Risk Register — risk, severity, owner, status

AUTHORITY MATRIX
cex.create_account_plan · cex.record_stakeholder · cex.schedule_account_review · cex.flag_relationship_risk · cex.escalate_client_issue
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never change commercial terms or scope — route to Mitra and the human owner.
5. If the local model is down, report it honestly — do not fake output."""

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
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500], format=kwargs.get("output_format")))
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
            bus.publish_sync(BusEnvelope(
                event_type="cex.success",
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

    @authority_guard("cex.create_account_plan")
    def create_account_plan(self, client_id: str, objectives: list) -> dict:
        """Create an account plan."""
        return {
            "record_id": f"SNE-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "objectives": objectives,
            "action": "create_account_plan",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.record_stakeholder")
    def record_stakeholder(self, client_id: str, name: str, role: str) -> dict:
        """Record a client stakeholder."""
        return {
            "record_id": f"SNE-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "name": name,
            "role": role,
            "action": "record_stakeholder",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.schedule_account_review")
    def schedule_account_review(self, client_id: str, review_date: str) -> dict:
        """Schedule an account review."""
        return {
            "record_id": f"SNE-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "review_date": review_date,
            "action": "schedule_account_review",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.flag_relationship_risk")
    def flag_relationship_risk(self, client_id: str, risk: str, severity: str) -> dict:
        """Flag a relationship risk."""
        return {
            "record_id": f"SNE-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "risk": risk,
            "severity": severity,
            "action": "flag_relationship_risk",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.escalate_client_issue")
    def escalate_client_issue(self, client_id: str, issue: str) -> dict:
        """Escalate a client issue to Mitra."""
        return {
            "record_id": f"SNE-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "issue": issue,
            "action": "escalate_client_issue",
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
