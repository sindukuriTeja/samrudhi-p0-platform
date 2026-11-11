"""Yojana — Campaign Strategy Agent (SAM-AG-059).

Phase 2 content pilot agent. Owns campaign strategy: defines campaign themes,
messaging frameworks, target audiences, and campaign calendars under Aarya.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Yojana(BaseAgent):
    """Campaign Strategy Agent."""

    canonical_id = "SAM-AG-059"
    name = "Yojana"
    designation = "Campaign Strategy Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.define_campaign": True,
        "crt.set_messaging": True,
        "crt.plan_calendar": True,
        "crt.set_target_audience": True,
        "crt.escalate_campaign": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Yojana, the Campaign Strategy Agent (SAM-AG-059 · CRT-015) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-059 · Position: CRT-015
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own campaign strategy. Define campaign themes, messaging frameworks,
target audiences, and campaign calendars. Translate approved scope into
campaign plans that guide content production. Never fabricate strategy.

YOUR REGISTERS
1. Campaign Register — campaigns, themes, objectives, status
2. Messaging Framework Register — core messages, pillars, tone
3. Campaign Calendar Register — timeline, milestones, deliverables
4. Target Audience Register — segments, personas, channels
5. Campaign Performance Register — metrics, learnings

HARD RULES — NEVER VIOLATE
1. Never exceed approved campaign scope — route to human.
2. Never fabricate campaign metrics or audience data. Missing = "unavailable".
3. Never suppress a campaign risk or blocker.
4. Respect tenant isolation.
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
                text=f"[MODEL UNAVAILABLE] {e}. Yojana cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="crt.campaign",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.define_campaign")
    def define_campaign(
        self,
        client_id: str,
        title: str,
        objective: str,
        theme: str,
        duration: dict,
    ) -> dict:
        """Define a new campaign."""
        campaign_id = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "campaign_id": campaign_id,
            "client_id": client_id,
            "title": title,
            "objective": objective,
            "theme": theme,
            "duration": duration,
            "status": "draft",
            "defined_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.set_messaging")
    def set_messaging_framework(
        self,
        campaign_id: str,
        pillars: list,
        core_messages: list,
        tone: str,
    ) -> dict:
        """Set messaging framework for a campaign."""
        return {
            "campaign_id": campaign_id,
            "pillars": pillars,
            "core_messages": core_messages,
            "tone": tone,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.plan_calendar")
    def plan_campaign_calendar(
        self,
        campaign_id: str,
        milestones: list,
        deliverables: list,
    ) -> dict:
        """Plan campaign calendar with milestones."""
        calendar_id = f"CAL-{uuid.uuid4().hex[:6].upper()}"
        return {
            "calendar_id": calendar_id,
            "campaign_id": campaign_id,
            "milestones": milestones,
            "deliverables": deliverables,
            "status": "planned",
            "planned_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.set_target_audience")
    def set_target_audience(
        self,
        campaign_id: str,
        segments: list,
        personas: list,
        channels: list,
    ) -> dict:
        """Set target audience for a campaign."""
        return {
            "campaign_id": campaign_id,
            "segments": segments,
            "personas": personas,
            "channels": channels,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_campaign")
    def escalate_campaign_issue(
        self,
        campaign_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a campaign issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "campaign_id": campaign_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_campaigns(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List campaigns (read-only)."""
        return {
            "campaigns": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_campaign_detail(
        self,
        campaign_id: str,
    ) -> dict:
        """Get campaign details (read-only)."""
        return {
            "campaign_id": campaign_id,
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
