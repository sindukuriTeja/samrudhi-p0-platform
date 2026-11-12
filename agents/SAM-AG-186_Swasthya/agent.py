"""Swasthya — Healthcare Content & Advertising Compliance (SAM-AG-186 · GOV-012).

Stage 1C assurance agent (P0). Role agent (evaluator): may use the model to read and judge, never to produce the work it assesses.
Independently screen healthcare content for medical-claim and advertising compliance;
block high-risk claims such as guaranteed cures. This is screening, not clinical
approval. [PDF 01A.11 · GOV-012 Healthcare Content & Advertising Compliance; GOV-P16,
GOV-P17]
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
class Swasthya(BaseAgent):
    """Healthcare Content & Advertising Compliance."""

    canonical_id = "SAM-AG-186"
    name = "Swasthya"
    designation = "Healthcare Content & Advertising Compliance"
    agent_type = "role"
    # Phrases blocked for healthcare marketing (Blueprint pilot exclusions: no unsupported
    # clinical outcomes or guarantees). Clients can add their own forbidden claims.
    HIGH_RISK_CLAIMS = (
        "guaranteed cure", "guarantees a cure", "100% cure", "cures diabetes", "cure diabetes",
        "reverses diabetes", "reverse diabetes", "reverses heart disease", "miracle", "permanent cure",
        "no side effects", "risk-free", "instant results", "clinically proven to cure",
        "stop taking your medication", "replace your medicine",
    )

    AUTHORITY = {
        "gov.screen_claims": True,
        "gov.block_content": True,
        "gov.record_compliance_result": True,
        "gov.escalate_clinical_risk": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "screen_claims": "gov.screen_claims",
        "block_content": "gov.block_content",
        "record_compliance_result": "gov.record_compliance_result",
        "escalate_clinical_risk": "gov.escalate_clinical_risk",
    }

    SYSTEM_PROMPT = """You are Swasthya, Healthcare Content & Advertising Compliance (SAM-AG-186 · GOV-012) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-186 · Position: GOV-012 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Independently screen healthcare content for medical-claim and advertising compliance; block
high-risk claims such as guaranteed cures. This is screening, not clinical approval. [PDF 01A.11
· GOV-012 Healthcare Content & Advertising Compliance; GOV-P16, GOV-P17]

YOUR REGISTERS
1. Claim Screening Register — content, flags, result
2. Blocked Content Register — content, reason, date

AUTHORITY MATRIX
gov.screen_claims · gov.block_content · gov.record_compliance_result · gov.escalate_clinical_risk
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. You are independent: you never produce the content or work you assess.
5. Never certify an agent — certification needs Satya and a human (gov.certify is denied).
6. Report critical risks to Satya and, through Sankat, to the Board.
7. High-risk claims are blocked by code, not by judgement alone.
8. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "screen")
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
                text=f"[MODEL UNAVAILABLE] {e}. Swasthya cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.healthcare_compliance",
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
    # Swasthya's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.screen_claims")
    def screen_claims(self, content: str, extra_forbidden: list = None) -> dict:
        """Flag high-risk healthcare claims."""
        text = (content or "").lower()
        patterns = list(self.HIGH_RISK_CLAIMS) + [p.lower() for p in (extra_forbidden or [])]
        flags = [p for p in patterns if p in text]
        return {
            "screening_id": f"SCR-{uuid.uuid4().hex[:6].upper()}",
            "flags": flags,
            "passed": not flags,
            "status": "pass" if not flags else "block",
            "screened_at": _now(),
        }

    @authority_guard("gov.block_content")
    def block_content(self, content_ref: str, reason: str) -> dict:
        """Block content from release."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "content_ref": content_ref,
            "reason": reason,
            "action": "block_content",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.record_compliance_result")
    def record_compliance_result(self, content_ref: str, result: dict) -> dict:
        """Record a screening result."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "content_ref": content_ref,
            "result": result,
            "action": "record_compliance_result",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_clinical_risk")
    def escalate_clinical_risk(self, content_ref: str, risk: str) -> dict:
        """Escalate a clinical-claim risk."""
        return {
            "record_id": f"SWA-{uuid.uuid4().hex[:6].upper()}",
            "content_ref": content_ref,
            "risk": risk,
            "action": "escalate_clinical_risk",
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
