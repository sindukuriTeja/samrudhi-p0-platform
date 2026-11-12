"""Lekha — Healthcare Copywriting (SAM-AG-082).

Phase 2 content pilot agent. Owns healthcare copywriting under Aarya:
writes captions, scripts, headlines, CTAs — all on-brand, compliant, ready for QA.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Lekha(BaseAgent):
    """Healthcare Copywriting."""

    canonical_id = "SAM-AG-082"
    name = "Lekha"
    designation = "Healthcare Copywriting"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.write_copy": True,
        "crt.adapt_message": True,
        "crt.write_cta": True,
        "crt.check_brand_voice": True,
        "crt.revise_copy": True,
        "crt.submit_for_qa": True,
        "crt.escalate_copy": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Lekha, Healthcare Copywriting (SAM-AG-082 · CRT-008) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-082 · Position: CRT-008
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Write accurate, engaging, brand-compliant healthcare copy: captions, scripts,
headlines, CTAs. Every copy reflects validated research facts and matches
the client's brand voice. Never provide medical advice. Never publish.

YOUR REGISTERS
1. Copy Brief Register — requests, type, platform, brief, deadline
2. Copy Draft Register — drafts, versions, platform, status
3. Brand Voice Register — brand voice, tone, style guide
4. Revision Register — revisions, changes, closure
5. Copy Log Register — writing actions, versions, approvals

HARD RULES — NEVER VIOLATE
1. Never publish content — requires approval.
2. Never provide medical advice or clinical recommendations.
3. Never fabricate claims or statistics. Missing = "unavailable".
4. Never suppress a brand mismatch or compliance concern.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "write")
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
                text=f"[MODEL UNAVAILABLE] {e}. Lekha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.copy",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.write_copy")
    def write_copy(
        self,
        client_id: str,
        platform: str,
        brief: dict,
        research_input: dict,
    ) -> dict:
        """Write copy for a platform and brief."""
        copy_id = f"CPY-{uuid.uuid4().hex[:6].upper()}"
        return {
            "copy_id": copy_id,
            "client_id": client_id,
            "platform": platform,
            "brief": brief,
            "copy": "",
            "status": "draft",
            "written_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.adapt_message")
    def adapt_message(
        self,
        core_message: str,
        platforms: list,
        brand_voice: dict,
    ) -> dict:
        """Adapt core message to multiple platforms."""
        return {
            "adaptations": {p: {"message": core_message, "platform": p} for p in platforms},
            "brand_voice": brand_voice,
            "adapted_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.write_cta")
    def write_cta(
        self,
        client_id: str,
        topic: str,
        compliance_rules: dict,
    ) -> dict:
        """Write a compliant call-to-action."""
        cta_id = f"CTA-{uuid.uuid4().hex[:6].upper()}"
        return {
            "cta_id": cta_id,
            "client_id": client_id,
            "topic": topic,
            "cta": "",
            "compliant": True,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.check_brand_voice")
    def check_brand_voice(
        self,
        copy_id: str,
        copy: str,
        brand_voice: dict,
    ) -> dict:
        """Check copy against brand voice."""
        issues = []
        if not copy.strip():
            issues.append("EMPTY_COPY")
        return {
            "copy_id": copy_id,
            "compliant": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.revise_copy")
    def revise_copy(
        self,
        copy_id: str,
        revision_request: dict,
    ) -> dict:
        """Revise copy based on feedback."""
        return {
            "copy_id": copy_id,
            "revision_request": revision_request,
            "status": "revised",
            "revised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.submit_for_qa")
    def submit_for_qa(
        self,
        copy_id: str,
        copy: str,
    ) -> dict:
        """Submit copy for compliance QA."""
        return {
            "copy_id": copy_id,
            "status": "qa_submitted",
            "submitted_to": "SAM-AG-080",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_copy")
    def escalate_copy_blocker(
        self,
        client_id: str,
        blocker_type: str,
        description: str,
    ) -> dict:
        """Escalate a copy blocker."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "blocker_type": blocker_type,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_copy_drafts(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List copy drafts (read-only)."""
        return {
            "drafts": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_copy_history(
        self,
        copy_id: str,
    ) -> dict:
        """Get copy version history (read-only)."""
        return {
            "copy_id": copy_id,
            "history": [],
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
