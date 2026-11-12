"""Yogyata — Competency Assessment (SAM-AG-181 · GOV-007).

Stage 1C assurance agent (P0). Role agent (evaluator): may use the model to read and judge, never to produce the work it assesses.
Run competency tests and scenario assessments to verify an agent can do its scope of
work before deployment. [PDF 01A.11 · GOV-007 Agent Competency Assessment; GOV-P04]
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
class Yogyata(BaseAgent):
    """Competency Assessment."""

    canonical_id = "SAM-AG-181"
    name = "Yogyata"
    designation = "Competency Assessment"
    agent_type = "role"

    AUTHORITY = {
        "gov.run_competency_test": True,
        "gov.record_assessment": True,
        "gov.escalate_failed_assessment": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "run_competency_test": "gov.run_competency_test",
        "record_assessment": "gov.record_assessment",
        "escalate_failed_assessment": "gov.escalate_failed_assessment",
    }

    SYSTEM_PROMPT = """You are Yogyata, Competency Assessment (SAM-AG-181 · GOV-007) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-181 · Position: GOV-007 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Run competency tests and scenario assessments to verify an agent can do its scope of work before
deployment. [PDF 01A.11 · GOV-007 Agent Competency Assessment; GOV-P04]

YOUR REGISTERS
1. Assessment Register — agent, cases, pass rate, date

AUTHORITY MATRIX
gov.run_competency_test · gov.record_assessment · gov.escalate_failed_assessment
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
        action = kwargs.get("action", "assess")
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
                text=f"[MODEL UNAVAILABLE] {e}. Yogyata cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.assessment",
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
    # Yogyata's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.run_competency_test")
    def run_competency_test(self, agent_id: str, test_cases: list) -> dict:
        """Score test cases (expected vs actual)."""
        cases = test_cases or []
        passed = sum(1 for c in cases if c.get("expected") == c.get("actual"))
        rate = round(passed / len(cases), 3) if cases else 0.0
        return {
            "assessment_id": f"ASM-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "cases": len(cases),
            "passed": passed,
            "pass_rate": rate,
            "status": "assessed" if cases else "no_test_cases",
            "assessed_at": _now(),
        }

    @authority_guard("gov.record_assessment")
    def record_assessment(self, agent_id: str, result: dict) -> dict:
        """Record an assessment."""
        return {
            "record_id": f"YOG-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "result": result,
            "action": "record_assessment",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_failed_assessment")
    def escalate_failed_assessment(self, agent_id: str, reason: str) -> dict:
        """Escalate a failed assessment."""
        return {
            "record_id": f"YOG-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "reason": reason,
            "action": "escalate_failed_assessment",
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
