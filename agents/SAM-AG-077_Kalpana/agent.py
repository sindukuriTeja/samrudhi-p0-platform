"""Kalpana — Editorial Planning Lead (SAM-AG-077).

Phase 2 content pilot agent. Owns editorial planning under Aarya:
builds editorial calendars, plans content schedules, coordinates deadlines.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Kalpana(BaseAgent):
    """Editorial Planning Lead."""

    canonical_id = "SAM-AG-077"
    name = "Kalpana"
    designation = "Editorial Planning Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.build_editorial_calendar": True,
        "crt.plan_content_schedule": True,
        "crt.set_deadlines": True,
        "crt.track_schedule": True,
        "crt.escalate_scheduling": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Kalpana, Editorial Planning Lead (SAM-AG-077 · CRT-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-077 · Position: CRT-003
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own editorial planning. Build editorial calendars, plan content schedules,
coordinate deadlines. Ensure content flows smoothly through production.
Never fabricate schedule data. Never suppress scheduling conflicts.

YOUR REGISTERS
1. Editorial Calendar Register — calendars, periods, items
2. Content Schedule Register — scheduled content, timing, owners
3. Deadline Register — deadlines, status, slippage
4. Schedule Conflict Register — conflicts, resolutions
5. Editorial Escalation Register — blockers, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate schedule or deadline data. Missing = "unavailable".
2. Never suppress a scheduling conflict or slippage.
3. Respect tenant isolation.
4. Every schedule item has an owner and deadline.
5. Satya's findings are immutable to you — read-only.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "plan")
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
                text=f"[MODEL UNAVAILABLE] {e}. Kalpana cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.editorial",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.build_editorial_calendar")
    def build_editorial_calendar(
        self,
        client_id: str,
        period_start: str,
        period_end: str,
        items: list,
    ) -> dict:
        """Build an editorial calendar."""
        calendar_id = f"EDT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "calendar_id": calendar_id,
            "client_id": client_id,
            "period_start": period_start,
            "period_end": period_end,
            "items": items,
            "status": "draft",
            "built_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.plan_content_schedule")
    def plan_content_schedule(
        self,
        calendar_id: str,
        content_items: list,
    ) -> dict:
        """Plan content schedule for a calendar."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "calendar_id": calendar_id,
            "content_items": content_items,
            "status": "planned",
            "planned_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.set_deadlines")
    def set_deadlines(
        self,
        schedule_id: str,
        deadlines: dict,
    ) -> dict:
        """Set deadlines for schedule items."""
        return {
            "schedule_id": schedule_id,
            "deadlines": deadlines,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.track_schedule")
    def track_schedule(
        self,
        schedule_id: str,
    ) -> dict:
        """Track schedule status and slippage."""
        return {
            "schedule_id": schedule_id,
            "items": [],
            "slippage": [],
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_scheduling")
    def escalate_scheduling_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a scheduling issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_calendars(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List editorial calendars (read-only)."""
        return {
            "calendars": [],
            "count": 0,
            "filter": {"client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_schedule(
        self,
        schedule_id: str,
    ) -> dict:
        """Get schedule details (read-only)."""
        return {
            "schedule_id": schedule_id,
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
