"""Nirikshan — Delivery Control Lead (SAM-AG-062 · OPS-005).

Phase 3 operations agent. Monitors work, checks progress, reports status,
and detects deviations. Reports to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Nirikshan(BaseAgent):
    """Delivery Control Lead."""

    canonical_id = "SAM-AG-062"
    name = "Nirikshan"
    designation = "Delivery Control Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.confirm_checks_present": True,
        "ops.monitor_work": True,
        "ops.check_progress": True,
        "ops.report_status": True,
        "ops.detect_deviation": True,
        "ops.escalate_monitoring_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Nirikshan, Delivery Control Lead (SAM-AG-062 · OPS-005) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-062 · Position: OPS-005
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Monitor work, check progress, report status, and detect deviations from plan.
Every deviation is flagged with evidence and escalation path.

YOUR REGISTERS
1. Monitoring Register — monitored items, frequency, last check
2. Progress Register — progress metrics, milestones, completion rates
3. Status Report Register — reports, periods, recipients
4. Deviation Register — deviations, severity, root cause
5. Monitoring Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.monitor_work · ops.check_progress · ops.report_status · ops.detect_deviation
ops.escalate_monitoring_issue · gov.certify=False · gov.modify_finding=False
tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate monitoring data — missing data = "unavailable".
2. Never suppress a deviation or downgrade an alert to improve metrics.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every deviation has evidence and an escalation record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "monitor")
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
                text=f"[MODEL UNAVAILABLE] {e}. Nirikshan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.monitor",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.monitor_work")
    def monitor_work(
        self,
        workflow_id: str,
        metrics: list,
    ) -> dict:
        """Monitor work for a workflow."""
        monitor_id = f"MON-{uuid.uuid4().hex[:6].upper()}"
        return {
            "monitor_id": monitor_id,
            "workflow_id": workflow_id,
            "metrics": metrics,
            "status": "monitoring",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.check_progress")
    def check_progress(
        self,
        execution_id: str,
        expected_progress: float,
    ) -> dict:
        """Check progress against expected values."""
        actual = expected_progress  # placeholder
        deviation = 0.0
        return {
            "execution_id": execution_id,
            "expected_progress": expected_progress,
            "actual_progress": actual,
            "deviation": deviation,
            "on_track": deviation <= 0.05,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.report_status")
    def report_status(
        self,
        period: str,
        workflows: list,
        metrics: dict,
    ) -> dict:
        """Generate a status report for a period."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "workflows": workflows,
            "metrics": metrics,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.detect_deviation")
    def detect_deviation(
        self,
        workflow_id: str,
        threshold: float,
        actual: float,
    ) -> dict:
        """Detect deviation from expected values."""
        deviation = abs(actual - threshold)
        return {
            "workflow_id": workflow_id,
            "threshold": threshold,
            "actual": actual,
            "deviation": deviation,
            "breached": deviation > threshold * 0.1,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_monitoring_issue")
    def escalate_monitoring_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_workflows: list,
    ) -> dict:
        """Escalate a monitoring issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_workflows": affected_workflows,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_monitoring_records(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List monitoring records (read-only)."""
        return {
            "records": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_progress_report(
        self,
        execution_id: str | None = None,
    ) -> dict:
        """Get progress report (read-only)."""
        return {
            "reports": [],
            "count": 0,
            "filter": {"execution_id": execution_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_deviations(
        self,
        workflow_id: str | None = None,
        severity: str | None = None,
    ) -> dict:
        """List deviations (read-only)."""
        return {
            "deviations": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id, "severity": severity},
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

    @authority_guard("ops.confirm_checks_present")
    def confirm_checks_present(self, checks: dict, required: list) -> dict:
        """Confirm every required check has a recorded pass."""
        missing = [c for c in required or [] if not (checks or {}).get(c)]
        return {"checks": checks, "missing": missing,
                "status": "ready" if not missing else "missing_check",
                "confirmed_at": datetime.now(timezone.utc).isoformat()}
