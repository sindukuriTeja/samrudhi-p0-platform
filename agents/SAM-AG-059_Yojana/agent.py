"""Yojana — Delivery Planning Lead (SAM-AG-059 · OPS-002).

Stage 2 Phase 2 content-pilot agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Plan delivery: turn the brief and workflow into a delivery plan with workstreams,
milestones and monthly production plans, and govern progress against it. [PDF 01A.05 ·
OPS-002 Delivery Planning & Project Management Lead; processes OPS-P03, OPS-P04]
Reports to Daksh (AI COO, SAM-AG-002).
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
class Yojana(BaseAgent):
    """Delivery Planning Lead."""

    canonical_id = "SAM-AG-059"
    name = "Yojana"
    designation = "Delivery Planning Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.create_delivery_plan": True,
        "ops.set_milestone": True,
        "ops.plan_production": True,
        "ops.review_plan_progress": True,
        "ops.escalate_plan_risk": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "create_delivery_plan": "ops.create_delivery_plan",
        "set_milestone": "ops.set_milestone",
        "plan_monthly_production": "ops.plan_production",
        "review_plan_progress": "ops.review_plan_progress",
        "escalate_plan_risk": "ops.escalate_plan_risk",
    }

    SYSTEM_PROMPT = """You are Yojana, Delivery Planning Lead (SAM-AG-059 · OPS-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-059 · Position: OPS-002 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Plan delivery: turn the brief and workflow into a delivery plan with workstreams, milestones and
monthly production plans, and govern progress against it. [PDF 01A.05 · OPS-002 Delivery
Planning & Project Management Lead; processes OPS-P03, OPS-P04]

YOUR REGISTERS
1. Delivery Plan Register — client, workstreams, milestones, owner
2. Milestone Register — milestone, due date, status
3. Production Plan Register — month, volumes, deadlines

AUTHORITY MATRIX
ops.create_delivery_plan · ops.set_milestone · ops.plan_production · ops.review_plan_progress · ops.escalate_plan_risk
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never commit capacity that Niyojan and Kshamata have not confirmed.
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
                text=f"[MODEL UNAVAILABLE] {e}. Yojana cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.planning",
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
    # Yojana's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.create_delivery_plan")
    def create_delivery_plan(self, client_id: str, workstreams: list) -> dict:
        """Create the delivery plan."""
        return {
            "record_id": f"YOJ-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "workstreams": workstreams,
            "action": "create_delivery_plan",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.set_milestone")
    def set_milestone(self, plan_id: str, milestone: str, due_date: str) -> dict:
        """Add a milestone."""
        return {
            "record_id": f"YOJ-{uuid.uuid4().hex[:6].upper()}",
            "plan_id": plan_id,
            "milestone": milestone,
            "due_date": due_date,
            "action": "set_milestone",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.plan_production")
    def plan_monthly_production(self, client_id: str, month: str, volumes: dict) -> dict:
        """Plan the month's production."""
        return {
            "record_id": f"YOJ-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "month": month,
            "volumes": volumes,
            "action": "plan_monthly_production",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.review_plan_progress")
    def review_plan_progress(self, plan_id: str) -> dict:
        """Review progress against the plan."""
        return {
            "record_id": f"YOJ-{uuid.uuid4().hex[:6].upper()}",
            "plan_id": plan_id,
            "action": "review_plan_progress",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_plan_risk")
    def escalate_plan_risk(self, plan_id: str, risk: str) -> dict:
        """Escalate a delivery plan risk."""
        return {
            "record_id": f"YOJ-{uuid.uuid4().hex[:6].upper()}",
            "plan_id": plan_id,
            "risk": risk,
            "action": "escalate_plan_risk",
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
