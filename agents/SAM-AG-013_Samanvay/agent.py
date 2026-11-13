"""Samanvay — Executive Coordination (SAM-AG-013 · CEO-004).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Coordinate executive work: open the action list and decision log for each initiative,
delegate tasks to the accountable owners, track handoffs between executives, schedule
reviews, and close actions only with evidence. [PDF Document 01C · CEO-004 Executive
Coordination; SAM-ROLE-004]
Reports to Arjun (AI CEO, SAM-AG-001).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Samanvay(BaseAgent):
    """Executive Coordination."""

    canonical_id = "SAM-AG-013"
    name = "Samanvay"
    designation = "Executive Coordination"
    agent_type = "thinking"

    AUTHORITY = {
        "ceo.open_action_list": True,
        "ceo.assign_action": True,
        "ceo.log_decision": True,
        "ceo.schedule_review": True,
        "ceo.close_action": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "open_action_list": "ceo.open_action_list",
        "assign_action": "ceo.assign_action",
        "log_decision": "ceo.log_decision",
        "schedule_review": "ceo.schedule_review",
        "close_action": "ceo.close_action",
    }

    SYSTEM_PROMPT = """You are Samanvay, Executive Coordination (SAM-AG-013 · CEO-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-013 · Position: CEO-004 · Department: CEO Office & Enterprise Strategy
- You report to Arjun (AI CEO, SAM-AG-001).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Coordinate executive work: open the action list and decision log for each initiative, delegate
tasks to the accountable owners, track handoffs between executives, schedule reviews, and close
actions only with evidence. [PDF Document 01C · CEO-004 Executive Coordination; SAM-ROLE-004]

YOUR REGISTERS
1. Cross-Department Action Tracker — action, owner, due date, status, closure evidence
2. Executive Decision Log — decision, recommender, approver, follow-up
3. Review Schedule — review, participants, date, outcome

AUTHORITY MATRIX
ceo.open_action_list · ceo.assign_action · ceo.log_decision · ceo.schedule_review · ceo.close_action
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never approve decisions reserved for humans or for Arjun — record and route them.
5. Never close an action without closure evidence.
6. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "coordinate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Samanvay cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ceo.coordination",
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
    # Samanvay's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ceo.open_action_list")
    def open_action_list(self, project_ref: str, owners: list) -> dict:
        """Open the action list for an initiative."""
        return {
            "record_id": f"SAM-{uuid.uuid4().hex[:6].upper()}",
            "project_ref": project_ref,
            "owners": owners,
            "action": "open_action_list",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ceo.assign_action")
    def assign_action(self, action: str, owner: str, due_date: str) -> dict:
        """Assign an action to an accountable owner."""
        return {
            "record_id": f"SAM-{uuid.uuid4().hex[:6].upper()}",
            "action": action,
            "owner": owner,
            "due_date": due_date,
            "action": "assign_action",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ceo.log_decision")
    def log_decision(self, decision: str, approver: str) -> dict:
        """Record a decision and its approver."""
        return {
            "record_id": f"SAM-{uuid.uuid4().hex[:6].upper()}",
            "decision": decision,
            "approver": approver,
            "action": "log_decision",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ceo.schedule_review")
    def schedule_review(self, subject: str, review_date: str) -> dict:
        """Schedule an executive review."""
        return {
            "record_id": f"SAM-{uuid.uuid4().hex[:6].upper()}",
            "subject": subject,
            "review_date": review_date,
            "action": "schedule_review",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ceo.close_action")
    def close_action(self, action_id: str, evidence: str) -> dict:
        """Close an action with evidence."""
        return {
            "record_id": f"SAM-{uuid.uuid4().hex[:6].upper()}",
            "action_id": action_id,
            "evidence": evidence,
            "action": "close_action",
            "status": "recorded",
            "recorded_at": _now(),
        }

    # ------------------------------------------------------------------
    # Read-only and escalation
    # ------------------------------------------------------------------

    def list_records(self, register: str | None = None) -> dict:
        """List register records (read-only)."""
        return {
            "records": [],
            "count": 0,
            "filter": {"register": register},
            "queried_at": _now(),
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
            "routed_at": _now(),
        }
