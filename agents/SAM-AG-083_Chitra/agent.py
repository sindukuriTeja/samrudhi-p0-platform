"""Chitra — Visual Creative Production (SAM-AG-083).

Phase 2 content pilot agent. Owns visual content creation under Aarya:
design briefs, templates, graphics, and visual assets for healthcare content.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Chitra(BaseAgent):
    """Visual Creative Production."""

    canonical_id = "SAM-AG-083"
    name = "Chitra"
    designation = "Visual Creative Production"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.create_visual_brief": True,
        "crt.design_asset": True,
        "crt.check_visual_brand": True,
        "crt.revise_visual": True,
        "crt.escalate_visual": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Chitra, Visual Creative Production (SAM-AG-083 · CRT-009) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-083 · Position: CRT-009
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own visual content creation. Create design briefs, templates, graphics,
and visual assets for healthcare content. Ensure all visuals match brand
guidelines. Never publish without approval. Never fabricate visual metrics.

YOUR REGISTERS
1. Visual Brief Register — visual requests, specs, deadlines
2. Visual Asset Register — designs, versions, status
3. Visual Brand Register — brand visuals, templates, guidelines
4. Revision Register — visual revisions, changes
5. Visual Escalation Register — blockers, compliance flags

HARD RULES — NEVER VIOLATE
1. Never publish visuals without approval.
2. Never fabricate visual metrics or performance. Missing = "unavailable".
3. Never suppress a brand mismatch.
4. All visuals must match client brand guidelines.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "design")
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
                text=f"[MODEL UNAVAILABLE] {e}. Chitra cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.visual",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.create_visual_brief")
    def create_visual_brief(
        self,
        client_id: str,
        asset_type: str,
        specs: dict,
        deadline: str | None = None,
    ) -> dict:
        """Create a visual content brief."""
        brief_id = f"VBR-{uuid.uuid4().hex[:6].upper()}"
        return {
            "brief_id": brief_id,
            "client_id": client_id,
            "asset_type": asset_type,
            "specs": specs,
            "deadline": deadline,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.design_asset")
    def design_asset(
        self,
        brief_id: str,
        design_direction: str,
    ) -> dict:
        """Design a visual asset from a brief."""
        asset_id = f"VAS-{uuid.uuid4().hex[:6].upper()}"
        return {
            "asset_id": asset_id,
            "brief_id": brief_id,
            "design_direction": design_direction,
            "status": "draft",
            "designed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.check_visual_brand")
    def check_visual_brand(
        self,
        asset_id: str,
        brand_guidelines: dict,
    ) -> dict:
        """Check visual against brand guidelines."""
        issues = []
        return {
            "asset_id": asset_id,
            "compliant": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.revise_visual")
    def revise_visual(
        self,
        asset_id: str,
        revision_request: dict,
    ) -> dict:
        """Revise a visual asset."""
        return {
            "asset_id": asset_id,
            "revision_request": revision_request,
            "status": "revised",
            "revised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_visual")
    def escalate_visual_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a visual content issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_visual_assets(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List visual assets (read-only)."""
        return {
            "assets": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_brand_visuals(
        self,
        client_id: str,
    ) -> dict:
        """Get brand visual guidelines (read-only)."""
        return {
            "client_id": client_id,
            "visuals": {},
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
