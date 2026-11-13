"""Nishtha — Performance & Quality Assurance Lead (SAM-AG-177 · GOV-003).

Stage 1C assurance agent (P0). Service-first agent: runs in code only and never calls the model.
Own the method for independent evaluation of agent performance and quality, review
performance exceptions and run the weekly assurance review. [PDF 01A.11 · GOV-003 Agent
Performance & Quality Assurance Lead; GOV-P35, GOV-P36]
Reports to Satya (Chief Assurance Agent, SAM-AG-010).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Nishtha(BaseAgent):
    """Performance & Quality Assurance Lead."""

    canonical_id = "SAM-AG-177"
    name = "Nishtha"
    designation = "Performance & Quality Assurance Lead"
    agent_type = "service-first"

    AUTHORITY = {
        "gov.define_evaluation_method": True,
        "gov.record_weekly_assurance": True,
        "gov.review_performance_exception": True,
        "gov.escalate_quality_risk": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "define_evaluation_method": "gov.define_evaluation_method",
        "record_weekly_assurance": "gov.record_weekly_assurance",
        "review_performance_exception": "gov.review_performance_exception",
        "escalate_quality_risk": "gov.escalate_quality_risk",
    }

    SYSTEM_PROMPT = """You are Nishtha, Performance & Quality Assurance Lead (SAM-AG-177 · GOV-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-177 · Position: GOV-003 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own the method for independent evaluation of agent performance and quality, review performance
exceptions and run the weekly assurance review. [PDF 01A.11 · GOV-003 Agent Performance &
Quality Assurance Lead; GOV-P35, GOV-P36]

YOUR REGISTERS
1. Evaluation Method Register — method, scope, version
2. Performance Exception Register — agent, exception, status

AUTHORITY MATRIX
gov.define_evaluation_method · gov.record_weekly_assurance · gov.review_performance_exception · gov.escalate_quality_risk
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. You are independent: you never produce the content or work you assess.
5. Never certify an agent — certification needs Satya and a human (gov.certify is denied).
6. Report critical risks to Satya and, through Sankat, to the Board.
7. You never call the model; every result comes from code."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        """Service-first: runs one of its tools in code. Never calls the model."""
        import json
        action = kwargs.get("action", "assure")
        if action not in self.TOOLS:
            return AgentResult(
                text=(f"Nishtha is a service-first agent and runs in code only. "
                      f"Supported actions: {', '.join(self.TOOLS)}."),
                agent_id=self.canonical_id, tokens_used=0, status="completed",
            )
        try:
            result = getattr(self, action)(**kwargs.get("params", {}))
            text, status = json.dumps(result, default=str), "completed"
        except Exception as e:
            text, status = f"{action} failed: {e}", "failed"
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.performance",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task, "status": status},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status=status)

    # ------------------------------------------------------------------
    # Nishtha's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.define_evaluation_method")
    def define_evaluation_method(self, scope: str, method: str) -> dict:
        """Define an evaluation method."""
        return {
            "record_id": f"NIS-{uuid.uuid4().hex[:6].upper()}",
            "scope": scope,
            "method": method,
            "action": "define_evaluation_method",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.record_weekly_assurance")
    def record_weekly_assurance(self, week: str, summary: str) -> dict:
        """Record the weekly assurance review."""
        return {
            "record_id": f"NIS-{uuid.uuid4().hex[:6].upper()}",
            "week": week,
            "summary": summary,
            "action": "record_weekly_assurance",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.review_performance_exception")
    def review_performance_exception(self, agent_id: str, exception: str) -> dict:
        """Review a performance exception."""
        return {
            "record_id": f"NIS-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "exception": exception,
            "action": "review_performance_exception",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_quality_risk")
    def escalate_quality_risk(self, agent_id: str, risk: str) -> dict:
        """Escalate a quality risk."""
        return {
            "record_id": f"NIS-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "risk": risk,
            "action": "escalate_quality_risk",
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
