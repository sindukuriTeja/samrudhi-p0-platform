"""Gunvatta — Output Quality Evaluation (SAM-AG-183 · GOV-009).

Stage 1C assurance agent (P0). Role agent (evaluator): may use the model to read and judge, never to produce the work it assesses.
Independently evaluate the accuracy, completeness and quality of agent outputs. Gunvatta
scores; it never produces or edits the work, and never scores its own output. [PDF
01A.11 · GOV-009 Output Quality Evaluation; GOV-P09]
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
class Gunvatta(BaseAgent):
    """Output Quality Evaluation."""

    canonical_id = "SAM-AG-183"
    name = "Gunvatta"
    designation = "Output Quality Evaluation"
    agent_type = "role"

    AUTHORITY = {
        "gov.evaluate_output": True,
        "gov.record_defect": True,
        "gov.escalate_quality_failure": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "evaluate_output": "gov.evaluate_output",
        "record_defect": "gov.record_defect",
        "escalate_quality_failure": "gov.escalate_quality_failure",
    }

    SYSTEM_PROMPT = """You are Gunvatta, Output Quality Evaluation (SAM-AG-183 · GOV-009) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-183 · Position: GOV-009 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Independently evaluate the accuracy, completeness and quality of agent outputs. Gunvatta scores;
it never produces or edits the work, and never scores its own output. [PDF 01A.11 · GOV-009
Output Quality Evaluation; GOV-P09]

YOUR REGISTERS
1. Output Evaluation Register — output, producer, defects, result
2. Quality Defect Register — defect, severity, status

AUTHORITY MATRIX
gov.evaluate_output · gov.record_defect · gov.escalate_quality_failure
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
        action = kwargs.get("action", "evaluate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Gunvatta cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.quality",
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
    # Gunvatta's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.evaluate_output")
    def evaluate_output(self, content: str, producer_agent: str, required_elements: list = None) -> dict:
        """Evaluate an output (independence enforced)."""
        if producer_agent == self.canonical_id:
            raise ValueError("Independence rule: Gunvatta cannot evaluate its own output.")
        text = (content or "").strip()
        missing = [k for k in (required_elements or []) if k.lower() not in text.lower()]
        defects = []
        if not text:
            defects.append("EMPTY_OUTPUT")
        if missing:
            defects.append("MISSING_ELEMENTS")
        return {
            "evaluation_id": f"EVL-{uuid.uuid4().hex[:6].upper()}",
            "producer_agent": producer_agent,
            "missing_elements": missing,
            "defects": defects,
            "passed": not defects,
            "status": "evaluated",
            "evaluated_at": _now(),
        }

    @authority_guard("gov.record_defect")
    def record_defect(self, output_ref: str, defect: str, severity: str) -> dict:
        """Record a quality defect."""
        return {
            "record_id": f"GUN-{uuid.uuid4().hex[:6].upper()}",
            "output_ref": output_ref,
            "defect": defect,
            "severity": severity,
            "action": "record_defect",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_quality_failure")
    def escalate_quality_failure(self, output_ref: str, reason: str) -> dict:
        """Escalate a quality failure."""
        return {
            "record_id": f"GUN-{uuid.uuid4().hex[:6].upper()}",
            "output_ref": output_ref,
            "reason": reason,
            "action": "escalate_quality_failure",
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
