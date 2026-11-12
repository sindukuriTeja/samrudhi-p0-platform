"""Samadhan — Complaint & Escalation (SAM-AG-055).

Phase 3 Client Experience agent. Owns client resolution: handle complaints,
track resolution progress, report resolution status, and escalation of
resolution issues. Reports to Mitra (SAM-AG-004).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Samadhan(BaseAgent):
    """Complaint & Escalation."""

    canonical_id = "SAM-AG-055"
    name = "Samadhan"
    designation = "Complaint & Escalation"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.resolve_client_issue": True,
        "cex.handle_complaint": True,
        "cex.track_resolution": True,
        "cex.report_resolution": True,
        "cex.escalate_resolution_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Samadhan, Complaint & Escalation (SAM-AG-055 · CEX-013) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-055 · Position: CEX-013 · Legacy: SAM-EX-055
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client issue resolution: handle complaints, track resolution progress,
report resolution status, and escalate resolution issues. Every resolution
must be timely, complete and documented. Never fabricate resolution status
or suppress unresolved complaints.

YOUR FIVE REGISTERS
1. Resolution Register — issues, complaints, status per client
2. Complaint Handling Register — complaint details, owner, timeline
3. Resolution Tracking Register — progress, milestones, closure evidence
4. Resolution Report Register — metrics, SLA compliance, trends
5. Resolution Escalation Register — unresolved issues, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate resolution status or closure evidence. Missing = "unavailable".
2. Never close a complaint without documented resolution — route to human.
3. Never suppress an unresolved complaint to improve resolution rates.
4. Respect tenant isolation — never cross-client resolution leakage.
5. Satya's findings are immutable to you — read-only.
6. Every resolution has a timestamp, owner and closure record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "resolve")
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
                text=f"[MODEL UNAVAILABLE] {e}. Samadhan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.resolution",
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
    # Samadhan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.resolve_client_issue")
    def resolve_client_issue(
        self,
        client_id: str,
        issue_type: str,
        description: str,
        priority: str = "P2",
    ) -> dict:
        """Resolve a client issue."""
        resolution_id = f"RES-{uuid.uuid4().hex[:6].upper()}"
        return {
            "resolution_id": resolution_id,
            "client_id": client_id,
            "issue_type": issue_type,
            "description": description,
            "priority": priority,
            "status": "open",
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.handle_complaint")
    def handle_complaint(
        self,
        client_id: str,
        complaint_type: str,
        description: str,
        owner: str,
    ) -> dict:
        """Handle a client complaint."""
        complaint_id = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "complaint_id": complaint_id,
            "client_id": client_id,
            "complaint_type": complaint_type,
            "description": description,
            "owner": owner,
            "status": "assigned",
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.track_resolution")
    def track_resolution(
        self,
        resolution_id: str,
    ) -> dict:
        """Track resolution progress for an issue."""
        return {
            "resolution_id": resolution_id,
            "progress": "unknown",
            "milestones": [],
            "closure_evidence": None,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.report_resolution")
    def report_resolution(
        self,
        period: str,
        resolved_issues: list,
        open_issues: list,
        sla_breaches: list,
    ) -> dict:
        """Generate resolution status report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "resolved_issues": len(resolved_issues),
            "open_issues": len(open_issues),
            "sla_breaches": len(sla_breaches),
            "resolution_rate": "0%",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_resolution_issue")
    def escalate_resolution_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        unresolved_issues: list,
    ) -> dict:
        """Escalate a resolution issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "unresolved_issues": unresolved_issues,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_resolutions(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List resolution records (read-only)."""
        return {
            "resolutions": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_complaint_status(
        self,
        complaint_id: str,
    ) -> dict:
        """Get complaint handling status (read-only)."""
        return {
            "complaint_id": complaint_id,
            "status": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_resolution_metrics(
        self,
        period: str | None = None,
    ) -> dict:
        """Get resolution metrics (read-only)."""
        return {
            "period": period,
            "metrics": {},
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
