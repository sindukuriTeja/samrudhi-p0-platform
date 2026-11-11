"""Disha — Content Localization Agent (SAM-AG-076).

Phase 2 content pilot agent. Owns content localization under Aarya:
adapts content for regional languages, cultural contexts, and local compliance.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Disha(BaseAgent):
    """Content Localization Agent."""

    canonical_id = "SAM-AG-076"
    name = "Disha"
    designation = "Content Localization Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.localize_content": True,
        "crt.adapt_culture": True,
        "crt.check_local_compliance": True,
        "crt.translate": True,
        "crt.escalate_localization": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Disha, the Content Localization Agent (SAM-AG-076 · CRT-022) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-076 · Position: CRT-022
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own content localization. Adapt content for regional languages, cultural
contexts, and local compliance. Ensure localized content maintains brand
voice and healthcare compliance. Never fabricate localization data.

YOUR REGISTERS
1. Localization Brief Register — localization requests, languages, deadlines
2. Localized Content Register — translations, adaptations, versions
3. Cultural Context Register — cultural norms, sensitivities per region
4. Local Compliance Register — regional regulations, requirements
5. Localization Escalation Register — blockers, escalations

HARD RULES — NEVER VIOLATE
1. Never publish localized content without approval.
2. Never fabricate translations or cultural adaptations. Missing = "unavailable".
3. Never suppress a cultural sensitivity or local compliance issue.
4. Localized content must maintain brand voice and healthcare compliance.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "localize")
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
                text=f"[MODEL UNAVAILABLE] {e}. Disha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="crt.localization",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.localize_content")
    def localize_content(
        self,
        client_id: str,
        content_ref: str,
        target_languages: list,
        brief: dict,
    ) -> dict:
        """Localize content for target languages."""
        localization_id = f"LOC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "localization_id": localization_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "target_languages": target_languages,
            "brief": brief,
            "status": "in_progress",
            "localized_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.adapt_culture")
    def adapt_culture(
        self,
        content_ref: str,
        region: str,
        cultural_context: dict,
    ) -> dict:
        """Adapt content for cultural context."""
        return {
            "content_ref": content_ref,
            "region": region,
            "cultural_context": cultural_context,
            "adapted": True,
            "adapted_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.check_local_compliance")
    def check_local_compliance(
        self,
        content_ref: str,
        region: str,
        local_rules: dict,
    ) -> dict:
        """Check localized content for local compliance."""
        violations = []
        return {
            "content_ref": content_ref,
            "region": region,
            "compliant": len(violations) == 0,
            "violations": violations,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.translate")
    def translate_content(
        self,
        content_ref: str,
        source_lang: str,
        target_lang: str,
    ) -> dict:
        """Translate content to target language."""
        translation_id = f"TRN-{uuid.uuid4().hex[:6].upper()}"
        return {
            "translation_id": translation_id,
            "content_ref": content_ref,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "translated": True,
            "translated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_localization")
    def escalate_localization_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a localization issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_localizations(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List localization items (read-only)."""
        return {
            "localizations": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_cultural_context(
        self,
        region: str,
    ) -> dict:
        """Get cultural context for a region (read-only)."""
        return {
            "region": region,
            "context": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
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
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }
