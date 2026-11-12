"""Pramana — Competency & Certification Lead (SAM-AG-176 · GOV-002).

Stage 1C assurance agent (P0). Service-first agent: runs in code only and never calls the model.
Set competency standards: what each agent must prove before it may do a scope of work,
certification policies and reassessment criteria. [PDF 01A.11 · GOV-002 Agent Competency
& Certification Lead; GOV-P02]
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
class Pramana(BaseAgent):
    """Competency & Certification Lead."""

    canonical_id = "SAM-AG-176"
    name = "Pramana"
    designation = "Competency & Certification Lead"
    agent_type = "service-first"

    AUTHORITY = {
        "gov.define_competency_standard": True,
        "gov.set_reassessment_criteria": True,
        "gov.review_test_design": True,
        "gov.escalate_competency_gap": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "define_competency_standard": "gov.define_competency_standard",
        "set_reassessment_criteria": "gov.set_reassessment_criteria",
        "review_test_design": "gov.review_test_design",
        "escalate_competency_gap": "gov.escalate_competency_gap",
    }

    SYSTEM_PROMPT = """You are Pramana, Competency & Certification Lead (SAM-AG-176 · GOV-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-176 · Position: GOV-002 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Set competency standards: what each agent must prove before it may do a scope of work,
certification policies and reassessment criteria. [PDF 01A.11 · GOV-002 Agent Competency &
Certification Lead; GOV-P02]

YOUR REGISTERS
1. Competency Standard Register — role, standard, level, version
2. Reassessment Criteria Register — trigger, scope

AUTHORITY MATRIX
gov.define_competency_standard · gov.set_reassessment_criteria · gov.review_test_design · gov.escalate_competency_gap
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
        action = kwargs.get("action", "standard")
        if action not in self.TOOLS:
            return AgentResult(
                text=(f"Pramana is a service-first agent and runs in code only. "
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
                event_type="gov.competency",
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
    # Pramana's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.define_competency_standard")
    def define_competency_standard(self, role: str, level: str, criteria: list) -> dict:
        """Define a competency standard."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "role": role,
            "level": level,
            "criteria": criteria,
            "action": "define_competency_standard",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.set_reassessment_criteria")
    def set_reassessment_criteria(self, role: str, triggers: list) -> dict:
        """Set reassessment triggers."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "role": role,
            "triggers": triggers,
            "action": "set_reassessment_criteria",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.review_test_design")
    def review_test_design(self, role: str, test_ref: str) -> dict:
        """Review a competency test design."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "role": role,
            "test_ref": test_ref,
            "action": "review_test_design",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_competency_gap")
    def escalate_competency_gap(self, agent_id: str, gap: str) -> dict:
        """Escalate a competency gap."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "gap": gap,
            "action": "escalate_competency_gap",
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
