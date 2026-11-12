"""Prakash — AI Compliance Verification Agent (SAM-AG-011).

Stage 1C assurance agent. Verifies that agent actions comply with policies,
regulations, and internal rules before they execute. Reports violations to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Prakash(BaseAgent):
    """AI Compliance Verification Agent."""

    canonical_id = "SAM-AG-011"
    name = "Prakash"
    designation = "AI Compliance Verification Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": False,
        "gov.verify_compliance": True,
        "gov.check_policy": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Prakash, the AI Compliance Verification Agent (SAM-AG-011).
You verify that agent actions comply with healthcare regulations (HIPAA, GDPR,
India's DPDP Act), internal policies, and data-handling rules BEFORE execution.

YOUR JOB: Pre-execution compliance checking. Review planned actions against
the policy registry. Block or flag non-compliant actions. Report violations
to Satya with evidence.

HARD RULES — NEVER VIOLATE:
1. Never approve an action you cannot verify against a written policy.
2. Patient data access requires explicit consent verification.
3. Cross-tenant data flow is always blocked unless explicitly authorized.
4. Report all violations — never suppress a compliance issue.
5. If the local model is down, report it honestly and block the action."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Prakash cannot verify compliance while Ollama is down. Action BLOCKED.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.compliance_check",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.verify_compliance")
    def check_action(
        self,
        action: str,
        actor_id: str,
        data_scope: str,
        tenant_id: str,
        consent_verified: bool = False,
    ) -> dict:
        """Verify an action against compliance policies."""
        violations = []
        # Basic compliance rules (deterministic pre-check)
        if data_scope == "patient_data" and not consent_verified:
            violations.append("PATIENT_CONSENT_MISSING")
        if data_scope == "cross_tenant":
            violations.append("CROSS_TENANT_BLOCKED")
        return {
            "check_id": f"CHK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "action": action,
            "actor_id": actor_id,
            "compliant": len(violations) == 0,
            "violations": violations,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
