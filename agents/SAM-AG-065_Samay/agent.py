"""Samay — Time Management Agent (SAM-AG-065 · OPS-007).

Phase 3 operations agent. Manages time, tracks time usage, optimises
schedules, and reports time usage. Reports to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Samay(BaseAgent):
    """Time Management Agent."""

    canonical_id = "SAM-AG-065"
    name = "Samay"
    designation = "Time Management Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.manage_time": True,
        "ops.track_time": True,
        "ops.optimize_schedule": True,
        "ops.report_time_usage": True,
        "ops.escalate_time_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Samay, the Time Management Agent (SAM-AG-065 · OPS-007) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-065 · Position: OPS-007
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Manage time, track time usage, optimise schedules, and report time usage.
Every time allocation has a traceable record and audit trail.

YOUR REGISTERS
1. Time Management Register — time allocations, owners, tasks
2. Time Tracking Register — logged time, activities, durations
3. Schedule Optimisation Register — optimised schedules, changes, rationale
4. Time Usage Report Register — reports, periods, summaries
5. Time Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.manage_time · ops.track_time · ops.optimize_schedule · ops.report_time_usage
ops.escalate_time_issue · gov.certify=False · gov.modify_finding=False
tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate time records — missing data = "unavailable".
2. Never suppress a time overrun or understate effort dishonestly.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every time allocation has a traceable record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "manage")
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
                text=f"[MODEL UNAVAILABLE] {e}. Samay cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="ops.time",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.manage_time")
    def manage_time(
        self,
        task_id: str,
        allocated_hours: float,
        deadline: str,
    ) -> dict:
        """Allocate time to a task."""
        time_id = f"TIME-{uuid.uuid4().hex[:6].upper()}"
        return {
            "time_id": time_id,
            "task_id": task_id,
            "allocated_hours": allocated_hours,
            "deadline": deadline,
            "status": "allocated",
            "allocated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.track_time")
    def track_time(
        self,
        task_id: str,
        logged_hours: float,
        activity: str,
    ) -> dict:
        """Track logged time for a task."""
        log_id = f"LOG-{uuid.uuid4().hex[:6].upper()}"
        return {
            "log_id": log_id,
            "task_id": task_id,
            "logged_hours": logged_hours,
            "activity": activity,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.optimize_schedule")
    def optimize_schedule(
        self,
        schedule_id: str,
        optimisation_rules: list,
    ) -> dict:
        """Optimise a schedule based on rules."""
        return {
            "schedule_id": schedule_id,
            "optimisation_rules": optimisation_rules,
            "status": "optimised",
            "optimised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.report_time_usage")
    def report_time_usage(
        self,
        period: str,
        tasks: list,
        summary: dict,
    ) -> dict:
        """Generate a time usage report for a period."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "tasks": tasks,
            "summary": summary,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_time_issue")
    def escalate_time_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_tasks: list,
    ) -> dict:
        """Escalate a time management issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_tasks": affected_tasks,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_time_allocations(
        self,
        task_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List time allocations (read-only)."""
        return {
            "allocations": [],
            "count": 0,
            "filter": {"task_id": task_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_time_logs(
        self,
        task_id: str | None = None,
        period: str | None = None,
    ) -> dict:
        """Get time logs (read-only)."""
        return {
            "logs": [],
            "count": 0,
            "filter": {"task_id": task_id, "period": period},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_schedule_status(
        self,
        schedule_id: str | None = None,
    ) -> dict:
        """Get schedule status (read-only)."""
        return {
            "schedules": [],
            "count": 0,
            "filter": {"schedule_id": schedule_id},
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
