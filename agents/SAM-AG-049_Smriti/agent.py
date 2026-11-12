"""Smriti — Content Knowledge / Client Context Agent (SAM-AG-049).

Phase 2 content pilot agent. Owns client context and content knowledge base:
captures client briefs, brand context, audience insights, and content history.
Provides the contextual foundation for all content production.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Smriti(BaseAgent):
    """Content Knowledge / Client Context Agent."""

    canonical_id = "SAM-AG-049"
    name = "Smriti"
    designation = "Client Knowledge"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.capture_context": True,
        "crt.store_knowledge": True,
        "crt.retrieve_context": True,
        "crt.update_brand_context": True,
        "crt.escalate_context_gap": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Smriti, Client Knowledge (SAM-AG-049 · CEX-007) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-049 · Position: CEX-007
- You report to Mitra (AI CXO, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own client context and content knowledge base. Capture client briefs, brand
context, audience insights, and content history. Provide the contextual
foundation for all content production. Never fabricate context — missing
data = "unavailable".

YOUR REGISTERS
1. Client Context Register — brief, brand, audience, history per client
2. Content Knowledge Register — past content, performance, learnings
3. Brand Context Register — voice, tone, style, compliance rules
4. Audience Insights Register — segments, preferences, behaviors
5. Context Gap Register — missing context, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate client context or audience data. Missing = "unavailable".
2. Never change approved commercial terms — route to human.
3. Never suppress a context gap to avoid escalation.
4. Respect tenant isolation — never cross-client context leakage.
5. Satya's findings are immutable to you — read-only.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "capture")
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
                text=f"[MODEL UNAVAILABLE] {e}. Smriti cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.context",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.capture_context")
    def capture_client_context(
        self,
        client_id: str,
        brief: dict,
        brand: dict,
        audience: dict,
    ) -> dict:
        """Capture client context and brand knowledge."""
        context_id = f"CTX-{uuid.uuid4().hex[:6].upper()}"
        return {
            "context_id": context_id,
            "client_id": client_id,
            "brief": brief,
            "brand": brand,
            "audience": audience,
            "status": "captured",
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.store_knowledge")
    def store_content_knowledge(
        self,
        client_id: str,
        content_ref: str,
        performance: dict,
        learnings: list,
    ) -> dict:
        """Store content performance knowledge."""
        knowledge_id = f"KNW-{uuid.uuid4().hex[:6].upper()}"
        return {
            "knowledge_id": knowledge_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "performance": performance,
            "learnings": learnings,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.retrieve_context")
    def get_client_context(
        self,
        client_id: str,
    ) -> dict:
        """Retrieve client context (read-only)."""
        return {
            "client_id": client_id,
            "context": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.update_brand_context")
    def update_brand_context(
        self,
        client_id: str,
        voice: dict,
        tone: dict,
        compliance_rules: dict,
    ) -> dict:
        """Update brand context for a client."""
        return {
            "client_id": client_id,
            "voice": voice,
            "tone": tone,
            "compliance_rules": compliance_rules,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_context_gap")
    def escalate_context_gap(
        self,
        client_id: str,
        gap_type: str,
        description: str,
    ) -> dict:
        """Escalate a context gap to human."""
        gap_id = f"GAP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "gap_id": gap_id,
            "client_id": client_id,
            "gap_type": gap_type,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_contexts(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List stored contexts (read-only)."""
        return {
            "contexts": [],
            "count": 0,
            "filter": {"client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_audience_insights(
        self,
        client_id: str,
    ) -> dict:
        """Get audience insights (read-only)."""
        return {
            "client_id": client_id,
            "insights": {},
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
