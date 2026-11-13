"""Sweekriti — Client Approval (SAM-AG-052 · CEX-010).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Run client approval and sign-off: build the approval request with its evidence, track
versions, route revision feedback, and record the decision made by the human approver.
Nothing is released without sign-off. [PDF 01A.04 · CEX-010 Client Approval & Sign-off;
processes CEX-P14]
Reports to Mitra (AI CXO, SAM-AG-004).
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
class Sweekriti(BaseAgent):
    """Client Approval."""

    canonical_id = "SAM-AG-052"
    name = "Sweekriti"
    designation = "Client Approval"
    agent_type = "thinking"
    REQUIRED_CHECKS = ("shuddhi", "pariksha", "gunvatta", "swasthya", "gopniya")

    AUTHORITY = {
        "cex.build_approval_request": True,
        "cex.record_client_decision": True,
        "cex.track_version": True,
        "cex.route_revision_feedback": True,
        "cex.escalate_approval_delay": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "build_approval_request": "cex.build_approval_request",
        "record_client_decision": "cex.record_client_decision",
        "track_version": "cex.track_version",
        "route_revision_feedback": "cex.route_revision_feedback",
        "escalate_approval_delay": "cex.escalate_approval_delay",
    }

    SYSTEM_PROMPT = """You are Sweekriti, Client Approval (SAM-AG-052 · CEX-010) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-052 · Position: CEX-010 · Department: Client Experience & Account Management
- You report to Mitra (AI CXO, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Run client approval and sign-off: build the approval request with its evidence, track versions,
route revision feedback, and record the decision made by the human approver. Nothing is released
without sign-off. [PDF 01A.04 · CEX-010 Client Approval & Sign-off; processes CEX-P14]

YOUR REGISTERS
1. Approval Request Register — content, evidence, approver, status
2. Version Register — item, version, change, date
3. Sign-off Evidence Register — decision, approver, timestamp

AUTHORITY MATRIX
cex.build_approval_request · cex.record_client_decision · cex.track_version · cex.route_revision_feedback · cex.escalate_approval_delay
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. You never approve content yourself — only a named human approver can.
5. Never send an approval request while required evidence is missing.
6. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "approval")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sweekriti cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.approval",
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
    # Sweekriti's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.build_approval_request")
    def build_approval_request(self, content_ref: str, evidence: dict) -> dict:
        """Build an approval request; blocks if evidence is missing."""
        missing = [c for c in self.REQUIRED_CHECKS if not (evidence or {}).get(c)]
        return {
            "request_id": f"APRQ-{uuid.uuid4().hex[:6].upper()}",
            "content_ref": content_ref,
            "evidence": evidence,
            "missing_evidence": missing,
            "status": "ready_for_human_approval" if not missing else "blocked_missing_evidence",
            "built_at": _now(),
        }

    @authority_guard("cex.record_client_decision")
    def record_client_decision(self, request_id: str, decision: str, approver: str) -> dict:
        """Record a decision made by a human approver."""
        if not approver:
            raise ValueError("A client decision must name the human approver; agents cannot approve.")
        if decision not in ("approve", "reject", "approve_with_changes"):
            raise ValueError(f"Unknown decision: {decision}")
        return {
            "request_id": request_id,
            "decision": decision,
            "approver": approver,
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.track_version")
    def track_version(self, item_ref: str, version: str) -> dict:
        """Track a content version."""
        return {
            "record_id": f"SWE-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "version": version,
            "action": "track_version",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.route_revision_feedback")
    def route_revision_feedback(self, item_ref: str, feedback: str) -> dict:
        """Send client feedback to the producing team."""
        return {
            "record_id": f"SWE-{uuid.uuid4().hex[:6].upper()}",
            "item_ref": item_ref,
            "feedback": feedback,
            "action": "route_revision_feedback",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("cex.escalate_approval_delay")
    def escalate_approval_delay(self, request_id: str, days_waiting: int) -> dict:
        """Escalate a delayed approval."""
        return {
            "record_id": f"SWE-{uuid.uuid4().hex[:6].upper()}",
            "request_id": request_id,
            "days_waiting": days_waiting,
            "action": "escalate_approval_delay",
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
