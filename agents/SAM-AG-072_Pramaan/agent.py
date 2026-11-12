"""Pramaan — Delivery Acceptance (SAM-AG-072 · OPS-015).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Confirm delivery readiness: verify that every required check and approval is present
before release, and refuse release when anything is missing. [PDF 01A.05 · OPS-015
Delivery Readiness & Acceptance; processes OPS-P21, OPS-P22]
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
class Pramaan(BaseAgent):
    """Delivery Acceptance."""

    canonical_id = "SAM-AG-072"
    name = "Pramaan"
    designation = "Delivery Acceptance"
    agent_type = "thinking"
    REQUIRED_CHECKS = ("shuddhi", "pariksha", "gunvatta", "swasthya", "gopniya")

    AUTHORITY = {
        "ops.verify_acceptance": True,
        "ops.confirm_release_readiness": True,
        "ops.record_acceptance_criteria": True,
        "ops.refuse_release": True,
        "ops.escalate_missing_approval": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "verify_acceptance": "ops.verify_acceptance",
        "confirm_release_readiness": "ops.confirm_release_readiness",
        "record_acceptance_criteria": "ops.record_acceptance_criteria",
        "refuse_release": "ops.refuse_release",
        "escalate_missing_approval": "ops.escalate_missing_approval",
    }

    SYSTEM_PROMPT = """You are Pramaan, Delivery Acceptance (SAM-AG-072 · OPS-015) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-072 · Position: OPS-015 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Confirm delivery readiness: verify that every required check and approval is present before
release, and refuse release when anything is missing. [PDF 01A.05 · OPS-015 Delivery Readiness &
Acceptance; processes OPS-P21, OPS-P22]

YOUR REGISTERS
1. Acceptance Register — item, checks, result, verifier
2. Release Readiness Register — item, ready, date

AUTHORITY MATRIX
ops.verify_acceptance · ops.confirm_release_readiness · ops.record_acceptance_criteria · ops.refuse_release · ops.escalate_missing_approval
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never confirm readiness while a required check is missing.
5. Nirikshan coordinates quality; you do not replace independent assurance.
6. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "verify")
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
                text=f"[MODEL UNAVAILABLE] {e}. Pramaan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.acceptance",
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
    # Pramaan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.verify_acceptance")
    def verify_acceptance(self, item_ref: str, checks: dict) -> dict:
        """Verify every required check is present."""
        missing = [c for c in self.REQUIRED_CHECKS if not (checks or {}).get(c)]
        return {
            "item_ref": item_ref,
            "checks": checks,
            "missing_checks": missing,
            "accepted": not missing,
            "status": "ready" if not missing else "refused_missing_check",
            "verified_at": _now(),
        }

    @authority_guard("ops.confirm_release_readiness")
    def confirm_release_readiness(self, item_ref: str) -> dict:
        """Confirm release readiness."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "action": "confirm_release_readiness",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.record_acceptance_criteria")
    def record_acceptance_criteria(self, item_ref: str, criteria: list) -> dict:
        """Record acceptance criteria."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "criteria": criteria,
            "action": "record_acceptance_criteria",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.refuse_release")
    def refuse_release(self, item_ref: str, reason: str) -> dict:
        """Refuse a release."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "reason": reason,
            "action": "refuse_release",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_missing_approval")
    def escalate_missing_approval(self, item_ref: str, missing: list) -> dict:
        """Escalate a missing approval."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "missing": missing,
            "action": "escalate_missing_approval",
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
