"""Punargathan — Rework Coordination (SAM-AG-071 · OPS-014).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Coordinate rework: when a checker or a human sends work back, create the rework request
with the reasons, assign it to the producing agent as a new round, count rounds and
escalate repeated revisions. [PDF 01A.05 · OPS-014 Rework & Revision Coordination]
Reports to Daksh (AI COO, SAM-AG-002).
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
class Punargathan(BaseAgent):
    """Rework Coordination."""

    canonical_id = "SAM-AG-071"
    name = "Punargathan"
    designation = "Rework Coordination"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.create_rework_request": True,
        "ops.assign_rework": True,
        "ops.track_revision": True,
        "ops.close_rework": True,
        "ops.escalate_repeat_revisions": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "create_rework_request": "ops.create_rework_request",
        "assign_rework": "ops.assign_rework",
        "track_revision": "ops.track_revision",
        "close_rework": "ops.close_rework",
        "escalate_repeat_revisions": "ops.escalate_repeat_revisions",
    }

    SYSTEM_PROMPT = """You are Punargathan, Rework Coordination (SAM-AG-071 · OPS-014) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-071 · Position: OPS-014 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Coordinate rework: when a checker or a human sends work back, create the rework request with the
reasons, assign it to the producing agent as a new round, count rounds and escalate repeated
revisions. [PDF 01A.05 · OPS-014 Rework & Revision Coordination]

YOUR REGISTERS
1. Rework Register — item, reasons, round, assignee, status
2. Revision Traceability Register — item, round, change, evidence

AUTHORITY MATRIX
ops.create_rework_request · ops.assign_rework · ops.track_revision · ops.close_rework · ops.escalate_repeat_revisions
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never overwrite an earlier round — every revision is a new round.
5. Escalate to a human when the round limit is exceeded.
6. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "rework")
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
                text=f"[MODEL UNAVAILABLE] {e}. Punargathan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.rework",
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
    # Punargathan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.create_rework_request")
    def create_rework_request(self, item_ref: str, reasons: list, round_no: int, max_rounds: int = 3) -> dict:
        """Create a rework request; escalates past the round limit."""
        escalate = round_no > max_rounds
        return {
            "rework_id": f"RWK-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "reasons": reasons,
            "round": round_no,
            "max_rounds": max_rounds,
            "status": "escalate_to_human" if escalate else "rework_requested",
            "requested_at": _now(),
        }

    @authority_guard("ops.assign_rework")
    def assign_rework(self, rework_id: str, agent_id: str) -> dict:
        """Assign rework to the producing agent."""
        return {
            "record_id": f"PUN-{uuid.uuid4().hex[:6].upper()}",
            "rework_id": rework_id,
            "agent_id": agent_id,
            "action": "assign_rework",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.track_revision")
    def track_revision(self, item_ref: str, round_no: int) -> dict:
        """Track a revision round."""
        return {
            "record_id": f"PUN-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "round_no": round_no,
            "action": "track_revision",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.close_rework")
    def close_rework(self, rework_id: str, evidence: str) -> dict:
        """Close rework with evidence."""
        return {
            "record_id": f"PUN-{uuid.uuid4().hex[:6].upper()}",
            "rework_id": rework_id,
            "evidence": evidence,
            "action": "close_rework",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_repeat_revisions")
    def escalate_repeat_revisions(self, item_ref: str, rounds: int) -> dict:
        """Escalate repeated revisions."""
        return {
            "record_id": f"PUN-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "rounds": rounds,
            "action": "escalate_repeat_revisions",
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
