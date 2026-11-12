"""Suchak — Delivery Early Warning (SAM-AG-070 · OPS-013).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Detect delivery exceptions early: missed or at-risk milestones, overdue steps and
delivery risks, and raise early warnings to Daksh before a deadline is missed. [PDF
01A.05 · OPS-013 Delivery Exception & Early Warning]
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
class Suchak(BaseAgent):
    """Delivery Early Warning."""

    canonical_id = "SAM-AG-070"
    name = "Suchak"
    designation = "Delivery Early Warning"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.check_milestone": True,
        "ops.raise_early_warning": True,
        "ops.classify_risk": True,
        "ops.record_exception": True,
        "ops.escalate_delivery_risk": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "check_milestone": "ops.check_milestone",
        "raise_early_warning": "ops.raise_early_warning",
        "classify_risk": "ops.classify_risk",
        "record_exception": "ops.record_exception",
        "escalate_delivery_risk": "ops.escalate_delivery_risk",
    }

    SYSTEM_PROMPT = """You are Suchak, Delivery Early Warning (SAM-AG-070 · OPS-013) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-070 · Position: OPS-013 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Detect delivery exceptions early: missed or at-risk milestones, overdue steps and delivery
risks, and raise early warnings to Daksh before a deadline is missed. [PDF 01A.05 · OPS-013
Delivery Exception & Early Warning]

YOUR REGISTERS
1. Early Warning Register — warning, milestone, severity, owner
2. Delivery Exception Register — exception, cause, status
3. Risk Classification Register — risk, class, severity

AUTHORITY MATRIX
ops.check_milestone · ops.raise_early_warning · ops.classify_risk · ops.record_exception · ops.escalate_delivery_risk
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never suppress a warning to make a schedule look healthy.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "monitor")
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
                text=f"[MODEL UNAVAILABLE] {e}. Suchak cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.early_warning",
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
    # Suchak's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.check_milestone")
    def check_milestone(self, milestone: str, due_iso: str, done: bool = False) -> dict:
        """Check whether a milestone is late."""
        due = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        late = (not done) and datetime.now(timezone.utc) > due
        return {
            "milestone": milestone,
            "due": due.isoformat(),
            "done": done,
            "late": late,
            "status": "warning" if late else "on_track" if not done else "done",
            "checked_at": _now(),
        }

    @authority_guard("ops.raise_early_warning")
    def raise_early_warning(self, milestone: str, reason: str) -> dict:
        """Raise an early warning."""
        return {
            "record_id": f"SUC-{uuid.uuid4().hex[:6].upper()}",
            "milestone": milestone,
            "reason": reason,
            "action": "raise_early_warning",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.classify_risk")
    def classify_risk(self, risk: str, severity: str) -> dict:
        """Classify a delivery risk."""
        return {
            "record_id": f"SUC-{uuid.uuid4().hex[:6].upper()}",
            "risk": risk,
            "severity": severity,
            "action": "classify_risk",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.record_exception")
    def record_exception(self, exception: str, cause: str) -> dict:
        """Record a delivery exception."""
        return {
            "record_id": f"SUC-{uuid.uuid4().hex[:6].upper()}",
            "exception": exception,
            "cause": cause,
            "action": "record_exception",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_delivery_risk")
    def escalate_delivery_risk(self, risk: str) -> dict:
        """Escalate a delivery risk to Daksh."""
        return {
            "record_id": f"SUC-{uuid.uuid4().hex[:6].upper()}",
            "risk": risk,
            "action": "escalate_delivery_risk",
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
