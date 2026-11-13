"""Pramanik — Certification & Recertification (SAM-AG-182 · GOV-008).

Stage 1C assurance agent (P0). Role agent (evaluator): may use the model to read and judge, never to produce the work it assesses.
Track certification status, recommend certification from assessment evidence, schedule
recertification and flag expired certificates. Pramanik recommends; it never certifies.
[PDF 01A.11 · GOV-008 Agent Certification & Recertification; GOV-P06, GOV-P07]
Reports to Satya (Chief Assurance Agent, SAM-AG-010).
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
class Pramanik(BaseAgent):
    """Certification & Recertification."""

    canonical_id = "SAM-AG-182"
    name = "Pramanik"
    designation = "Certification & Recertification"
    agent_type = "role"

    AUTHORITY = {
        "gov.recommend_certification": True,
        "gov.schedule_recertification": True,
        "gov.track_certificate_expiry": True,
        "gov.escalate_expired_certificate": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "recommend_certification": "gov.recommend_certification",
        "schedule_recertification": "gov.schedule_recertification",
        "track_certificate_expiry": "gov.track_certificate_expiry",
        "escalate_expired_certificate": "gov.escalate_expired_certificate",
    }

    SYSTEM_PROMPT = """You are Pramanik, Certification & Recertification (SAM-AG-182 · GOV-008) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-182 · Position: GOV-008 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Track certification status, recommend certification from assessment evidence, schedule
recertification and flag expired certificates. Pramanik recommends; it never certifies. [PDF
01A.11 · GOV-008 Agent Certification & Recertification; GOV-P06, GOV-P07]

YOUR REGISTERS
1. Certification Register — agent, scope, status, expiry
2. Recertification Schedule — agent, due date

AUTHORITY MATRIX
gov.recommend_certification · gov.schedule_recertification · gov.track_certificate_expiry · gov.escalate_expired_certificate
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. You are independent: you never produce the content or work you assess.
5. Never certify an agent — certification needs Satya and a human (gov.certify is denied).
6. Report critical risks to Satya and, through Sankat, to the Board.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "certify_review")
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
                text=f"[MODEL UNAVAILABLE] {e}. Pramanik cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.certification",
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
    # Pramanik's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.recommend_certification")
    def recommend_certification(self, agent_id: str, assessment_pass_rate: float, min_rate: float = 0.9) -> dict:
        """Recommend (not grant) certification."""
        recommended = assessment_pass_rate >= min_rate
        return {
            "agent_id": agent_id,
            "pass_rate": assessment_pass_rate,
            "min_rate": min_rate,
            "recommendation": "certify" if recommended else "do_not_certify",
            # Pramanik only recommends: certification needs Satya and a human (gov.certify is denied).
            "status": "recommended_pending_human" if recommended else "not_recommended",
            "recommended_at": _now(),
        }

    @authority_guard("gov.schedule_recertification")
    def schedule_recertification(self, agent_id: str, due_date: str) -> dict:
        """Schedule recertification."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "due_date": due_date,
            "action": "schedule_recertification",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.track_certificate_expiry")
    def track_certificate_expiry(self, agent_id: str, expires: str) -> dict:
        """Track certificate expiry."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "expires": expires,
            "action": "track_certificate_expiry",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_expired_certificate")
    def escalate_expired_certificate(self, agent_id: str) -> dict:
        """Escalate an expired certificate."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "action": "escalate_expired_certificate",
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
