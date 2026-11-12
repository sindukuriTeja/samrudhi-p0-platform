"""Roop — Creative Production Lead (SAM-AG-078).

Phase 2 content pilot agent. Owns creative briefs under Aarya:
creates design briefs, visual specifications, and creative direction for content production.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Roop(BaseAgent):
    """Creative Production Lead."""

    canonical_id = "SAM-AG-078"
    name = "Roop"
    designation = "Creative Production Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.create_creative_brief": True,
        "crt.set_visual_specs": True,
        "crt.define_creative_direction": True,
        "crt.review_brief": True,
        "crt.escalate_brief": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Roop, Creative Production Lead (SAM-AG-078 · CRT-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-078 · Position: CRT-004
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own creative briefs. Create design briefs, visual specifications, and creative
direction for content production. Ensure briefs are clear, complete, and aligned
with brand guidelines. Never fabricate brief data.

YOUR REGISTERS
1. Creative Brief Register — briefs, specs, status
2. Visual Specs Register — dimensions, formats, requirements
3. Creative Direction Register — direction, mood, style
4. Brief Revision Register — revisions, changes
5. Brief Escalation Register — gaps, escalations

HARD RULES — NEVER VIOLATE
1. Never publish content — briefs only.
2. Never fabricate brief or spec data. Missing = "unavailable".
3. Never suppress a brief gap or ambiguity.
4. All briefs must align with brand guidelines.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "create")
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
                text=f"[MODEL UNAVAILABLE] {e}. Roop cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.brief",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.create_creative_brief")
    def create_creative_brief(
        self,
        client_id: str,
        content_type: str,
        objective: str,
        requirements: dict,
    ) -> dict:
        """Create a creative brief."""
        brief_id = f"CRB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "brief_id": brief_id,
            "client_id": client_id,
            "content_type": content_type,
            "objective": objective,
            "requirements": requirements,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.set_visual_specs")
    def set_visual_specs(
        self,
        brief_id: str,
        dimensions: dict,
        formats: list,
        file_specs: dict,
    ) -> dict:
        """Set visual specifications for a brief."""
        return {
            "brief_id": brief_id,
            "dimensions": dimensions,
            "formats": formats,
            "file_specs": file_specs,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.define_creative_direction")
    def define_creative_direction(
        self,
        brief_id: str,
        mood: str,
        style: str,
        references: list,
    ) -> dict:
        """Define creative direction for a brief."""
        return {
            "brief_id": brief_id,
            "mood": mood,
            "style": style,
            "references": references,
            "defined_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.review_brief")
    def review_brief(
        self,
        brief_id: str,
        review_criteria: dict,
    ) -> dict:
        """Review a creative brief for completeness."""
        score = sum(review_criteria.values()) / len(review_criteria) if review_criteria else 0
        return {
            "brief_id": brief_id,
            "score": round(score, 2),
            "criteria": review_criteria,
            "status": "reviewed",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_brief")
    def escalate_brief_gap(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a brief gap."""
        gap_id = f"GAP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "gap_id": gap_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_briefs(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List creative briefs (read-only)."""
        return {
            "briefs": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_brief_detail(
        self,
        brief_id: str,
    ) -> dict:
        """Get brief details (read-only)."""
        return {
            "brief_id": brief_id,
            "details": {},
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
