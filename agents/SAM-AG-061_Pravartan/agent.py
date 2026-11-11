"""Pravartan — Work Execution Agent (SAM-AG-061 · OPS-004).

Phase 3 operations agent. Executes work, assigns tasks, tracks execution,
and completes work. Reports to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Pravartan(BaseAgent):
    """Work Execution Agent."""

    canonical_id = "SAM-AG-061"
    name = "Pravartan"
    designation = "Work Execution Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.execute_work": True,
        "ops.assign_tasks": True,
        "ops.track_execution": True,
        "ops.complete_work": True,
        "ops.escalate_execution_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Pravartan, the Work Execution Agent (SAM-AG-061 · OPS-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-061 · Position: OPS-004
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Execute work, assign tasks, track execution progress, and complete work.
Every assigned task moves through execution to closure with evidence.

YOUR REGISTERS
1. Execution Register — active executions, owners, progress
2. Task Assignment Register — assignments, owners, deadlines
3. Execution Tracking Register — progress, milestones, blockers
4. Work Completion Register — completed work, evidence, sign-off
5. Execution Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.execute_work · ops.assign_tasks · ops.track_execution · ops.complete_work
ops.escalate_execution_issue · gov.certify=False · gov.modify_finding=False
tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate execution progress — missing data = "unavailable".
2. Never suppress an execution failure or claim completion without evidence.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every completed task has closure evidence.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "execute")
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
                text=f"[MODEL UNAVAILABLE] {e}. Pravartan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="ops.execute",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.execute_work")
    def execute_work(
        self,
        task_id: str,
        assigned_agent: str,
        execution_plan: dict,
    ) -> dict:
        """Execute a work task."""
        exec_id = f"EXEC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "execution_id": exec_id,
            "task_id": task_id,
            "assigned_agent": assigned_agent,
            "execution_plan": execution_plan,
            "status": "executing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.assign_tasks")
    def assign_tasks(
        self,
        task_id: str,
        assigned_agent: str,
        deadline: str,
    ) -> dict:
        """Assign a task to an agent."""
        assignment_id = f"ASSIGN-{uuid.uuid4().hex[:6].upper()}"
        return {
            "assignment_id": assignment_id,
            "task_id": task_id,
            "assigned_agent": assigned_agent,
            "deadline": deadline,
            "status": "assigned",
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.track_execution")
    def track_execution(
        self,
        execution_id: str,
        progress: float,
        status: str,
    ) -> dict:
        """Track execution progress."""
        return {
            "execution_id": execution_id,
            "progress": progress,
            "status": status,
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.complete_work")
    def complete_work(
        self,
        execution_id: str,
        evidence: str,
        closure_notes: str,
    ) -> dict:
        """Complete a work execution with evidence."""
        return {
            "execution_id": execution_id,
            "evidence": evidence,
            "closure_notes": closure_notes,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_execution_issue")
    def escalate_execution_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_executions: list,
    ) -> dict:
        """Escalate an execution issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_executions": affected_executions,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_executions(
        self,
        status: str | None = None,
    ) -> dict:
        """List executions (read-only)."""
        return {
            "executions": [],
            "count": 0,
            "filter": {"status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_assignments(
        self,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List task assignments (read-only)."""
        return {
            "assignments": [],
            "count": 0,
            "filter": {"agent_id": agent_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_execution_status(
        self,
        execution_id: str | None = None,
    ) -> dict:
        """Get execution status (read-only)."""
        return {
            "executions": [],
            "count": 0,
            "filter": {"execution_id": execution_id},
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
