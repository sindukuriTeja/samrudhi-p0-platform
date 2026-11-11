"""Lagaat — Content Continuity / Sales CRM Agent (SAM-AG-146).

Phase 2 content pilot agent. Owns content continuity and sales CRM integration
under Aarya: tracks content lifecycle, client CRM data, and content-sales handoff.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Lagaat(BaseAgent):
    """Content Continuity / Sales CRM Agent."""

    canonical_id = "SAM-AG-146"
    name = "Lagaat"
    designation = "Content Continuity Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.track_continuity": True,
        "crt.manage_crm_data": True,
        "crt.handoff_content": True,
        "crt.update_client_status": True,
        "crt.escalate_continuity": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Lagaat, the Content Continuity Agent (SAM-AG-146 · CRT-029) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-146 · Position: CRT-029
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own content continuity and sales CRM integration. Track content lifecycle,
client CRM data, and content-sales handoff. Ensure smooth flow from sales
to content production to delivery. Never fabricate CRM data.

YOUR REGISTERS
1. Content Continuity Register — content lifecycle, status, handoffs
2. CRM Data Register — client CRM records, status, notes
3. Handoff Register — sales-to-content handoffs, status
4. Client Status Register — client status, milestones
5. Continuity Escalation Register — blockers, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate CRM or continuity data. Missing = "unavailable".
2. Never suppress a handoff gap or continuity break.
3. Respect tenant isolation — no cross-client data leakage.
4. Never change commercial terms — route to human.
5. Satya's findings are immutable to you — read-only.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "track")
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
                text=f"[MODEL UNAVAILABLE] {e}. Lagaat cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="crt.continuity",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.track_continuity")
    def track_content_continuity(
        self,
        client_id: str,
        content_ref: str,
        lifecycle_stage: str,
    ) -> dict:
        """Track content lifecycle continuity."""
        continuity_id = f"CON-{uuid.uuid4().hex[:6].upper()}"
        return {
            "continuity_id": continuity_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "lifecycle_stage": lifecycle_stage,
            "status": "tracked",
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.manage_crm_data")
    def update_crm_data(
        self,
        client_id: str,
        field: str,
        value: Any,
    ) -> dict:
        """Update CRM data for a client."""
        return {
            "client_id": client_id,
            "field": field,
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.handoff_content")
    def handoff_content(
        self,
        client_id: str,
        content_ref: str,
        from_agent: str,
        to_agent: str,
    ) -> dict:
        """Hand off content between agents/stages."""
        handoff_id = f"HOF-{uuid.uuid4().hex[:6].upper()}"
        return {
            "handoff_id": handoff_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "status": "handed_off",
            "handed_off_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.update_client_status")
    def update_client_status(
        self,
        client_id: str,
        status: str,
        notes: str,
    ) -> dict:
        """Update client status in CRM."""
        return {
            "client_id": client_id,
            "status": status,
            "notes": notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_continuity")
    def escalate_continuity_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a continuity issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_continuity(
        self,
        client_id: str | None = None,
        lifecycle_stage: str | None = None,
    ) -> dict:
        """List content continuity records (read-only)."""
        return {
            "continuity": [],
            "count": 0,
            "filter": {"client_id": client_id, "lifecycle_stage": lifecycle_stage},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_crm_data(
        self,
        client_id: str,
    ) -> dict:
        """Get CRM data for a client (read-only)."""
        return {
            "client_id": client_id,
            "data": {},
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
