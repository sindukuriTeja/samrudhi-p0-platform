"""Chetak — Executive Support Agent (SAM-AG-130).

Phase 3 CEO Office agent. Owns executive support functions: briefing preparation,
scheduling, action item tracking, and executive issue escalation. Provides
administrative and coordination support to the CEO (Arjun).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Chetak(BaseAgent):
    """Executive Support Agent."""

    canonical_id = "SAM-AG-130"
    name = "Chetak"
    designation = "Executive Support Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ceo.provide_executive_support": True,
        "ceo.prepare_briefing": True,
        "ceo.schedule_executive": True,
        "ceo.track_action_items": True,
        "ceo.escalate_executive_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Chetak, the Executive Support Agent (SAM-AG-130 · CEO-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-130 · Position: CEO-004 · Legacy: SAM-EX-130
- You report to Arjun (AI CEO, SAM-AG-001). You do NOT report to any other agent.
- You own executive support: briefing preparation, scheduling, action tracking, escalation.
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Provide executive support to the CEO: prepare briefings, schedule executive
meetings, track action items to closure, and escalate executive issues.
Never fabricate briefing content — missing data = "unavailable". Never lose
an action item or suppress an escalation.

YOUR FIVE REGISTERS
1. Briefing Register — briefings prepared, topics, recipients, periods
2. Executive Schedule Register — meetings, attendees, agendas, outcomes
3. Action Item Register — items, owners, deadlines, status, closure evidence
4. Executive Support Register — support requests, tasks, status
5. Executive Escalation Register — issues escalated, severity, resolution

HARD RULES — NEVER VIOLATE
1. Never fabricate briefing content or meeting details. Missing = "unavailable".
2. Never lose an action item or mark it complete without closure evidence.
3. Never suppress an executive escalation to avoid discomfort.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every action item has an owner, deadline, and closure evidence.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "support")
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
                text=f"[MODEL UNAVAILABLE] {e}. Chetak cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ceo.executive_support",
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
    # Chetak's 5 domain tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ceo.prepare_briefing")
    def prepare_briefing(
        self,
        briefing_type: str,
        topics: list,
        period: str,
        recipients: list,
    ) -> dict:
        """Prepare an executive briefing."""
        briefing_id = f"BRIEF-{uuid.uuid4().hex[:6].upper()}"
        return {
            "briefing_id": briefing_id,
            "briefing_type": briefing_type,
            "topics": topics,
            "topic_count": len(topics),
            "period": period,
            "recipients": recipients,
            "status": "prepared",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.schedule_executive")
    def schedule_executive_meeting(
        self,
        title: str,
        attendees: list,
        agenda: list,
        scheduled_time: str,
    ) -> dict:
        """Schedule an executive meeting."""
        meeting_id = f"MTG-{uuid.uuid4().hex[:6].upper()}"
        return {
            "meeting_id": meeting_id,
            "title": title,
            "attendees": attendees,
            "agenda": agenda,
            "agenda_count": len(agenda),
            "scheduled_time": scheduled_time,
            "status": "scheduled",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.track_action_items")
    def track_action_item(
        self,
        title: str,
        owner: str,
        deadline: str,
        priority: str = "P1",
        closure_evidence: str | None = None,
    ) -> dict:
        """Track an executive action item."""
        action_id = f"ACT-{uuid.uuid4().hex[:6].upper()}"
        status = "closed" if closure_evidence else "open"
        return {
            "action_id": action_id,
            "title": title,
            "owner": owner,
            "deadline": deadline,
            "priority": priority,
            "closure_evidence": closure_evidence,
            "status": status,
            "tenant_id": "DEMO-HEALTHCARE-01",
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.provide_executive_support")
    def provide_executive_support(
        self,
        request_type: str,
        description: str,
        urgency: str,
        context: dict,
    ) -> dict:
        """Provide executive support for a request."""
        support_id = f"SUP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "support_id": support_id,
            "request_type": request_type,
            "description": description,
            "urgency": urgency,
            "context": context,
            "status": "provided",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "provided_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.escalate_executive_issue")
    def escalate_executive_issue(
        self,
        issue_type: str,
        severity: str,
        description: str,
        affected_areas: list,
    ) -> dict:
        """Escalate an executive issue to human."""
        escalation_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "escalation_id": escalation_id,
            "issue_type": issue_type,
            "severity": severity,  # S1..S4
            "description": description,
            "affected_areas": affected_areas,
            "status": "escalated",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Read-only methods (no authority guard needed)
    # ------------------------------------------------------------------

    def list_briefings(
        self,
        briefing_type: str | None = None,
        period: str | None = None,
    ) -> dict:
        """List prepared briefings (read-only)."""
        return {
            "briefings": [],
            "count": 0,
            "filter": {"briefing_type": briefing_type, "period": period},
            "tenant_id": "DEMO-HEALTHCARE-01",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_meetings(
        self,
        status: str | None = None,
        scheduled_time: str | None = None,
    ) -> dict:
        """List scheduled meetings (read-only)."""
        return {
            "meetings": [],
            "count": 0,
            "filter": {"status": status, "scheduled_time": scheduled_time},
            "tenant_id": "DEMO-HEALTHCARE-01",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_action_items(
        self,
        owner: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List action items (read-only)."""
        return {
            "action_items": [],
            "count": 0,
            "filter": {"owner": owner, "status": status},
            "tenant_id": "DEMO-HEALTHCARE-01",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_executive_escalations(
        self,
        status: str | None = None,
    ) -> dict:
        """List executive escalations (read-only)."""
        return {
            "escalations": [],
            "count": 0,
            "filter": {"status": status},
            "tenant_id": "DEMO-HEALTHCARE-01",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Route for approval (outside delegated authority)
    # ------------------------------------------------------------------

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
