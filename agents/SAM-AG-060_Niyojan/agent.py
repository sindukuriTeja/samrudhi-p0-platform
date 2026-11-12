"""Niyojan — Work Planning Agent (SAM-AG-060 · OPS-003).

Phase 3 operations agent. Plans work, defines tasks, sets priorities, and
schedules work. Reports to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Niyojan(BaseAgent):
    """Work Planning Agent."""

    canonical_id = "SAM-AG-060"
    name = "Niyojan"
    designation = "Work Planning Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.plan_work": True,
        "ops.define_tasks": True,
        "ops.set_priorities": True,
        "ops.schedule_work": True,
        "ops.escalate_planning_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Niyojan, the Work Planning Agent (SAM-AG-060 · OPS-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-060 · Position: OPS-003
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Plan work, define tasks, set priorities, and schedule work. Every approved
scope becomes a structured plan with tasks, owners, priorities and deadlines.

YOUR REGISTERS
1. Work Plan Register — plans, scope, stages, deadlines
2. Task Register — task definitions, owners, dependencies
3. Priority Register — priority levels, rationale, changes
4. Schedule Register — timelines, milestones, allocations
5. Planning Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.plan_work · ops.define_tasks · ops.set_priorities · ops.schedule_work
ops.escalate_planning_issue · gov.certify=False · gov.modify_finding=False
tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate plan status — missing data = "unavailable".
2. Never suppress a planning gap or underestimate effort dishonestly.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every task has an owner, priority and deadline.
7. If the local model is down, report it honestly — do not fake output."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Niyojan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.plan",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.plan_work")
    def plan_work(
        self,
        workflow_id: str,
        scope: str,
        phases: list,
    ) -> dict:
        """Create a work plan for a workflow."""
        plan_id = f"PLAN-{uuid.uuid4().hex[:6].upper()}"
        return {
            "plan_id": plan_id,
            "workflow_id": workflow_id,
            "scope": scope,
            "phases": phases,
            "status": "planned",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.define_tasks")
    def define_tasks(
        self,
        plan_id: str,
        tasks: list,
    ) -> dict:
        """Define tasks within a work plan."""
        task_group_id = f"TASK-{uuid.uuid4().hex[:6].upper()}"
        return {
            "task_group_id": task_group_id,
            "plan_id": plan_id,
            "tasks": tasks,
            "count": len(tasks),
            "defined_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.set_priorities")
    def set_priorities(
        self,
        plan_id: str,
        priorities: dict,
    ) -> dict:
        """Set priorities for tasks in a plan."""
        return {
            "plan_id": plan_id,
            "priorities": priorities,
            "status": "prioritised",
            "set_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.schedule_work")
    def schedule_work(
        self,
        plan_id: str,
        schedule: dict,
    ) -> dict:
        """Schedule work with timelines and milestones."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "plan_id": plan_id,
            "schedule": schedule,
            "status": "scheduled",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_planning_issue")
    def escalate_planning_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_plans: list,
    ) -> dict:
        """Escalate a planning issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_plans": affected_plans,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_plans(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List work plans (read-only)."""
        return {
            "plans": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_tasks(
        self,
        plan_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List tasks (read-only)."""
        return {
            "tasks": [],
            "count": 0,
            "filter": {"plan_id": plan_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_schedule_status(
        self,
        plan_id: str | None = None,
    ) -> dict:
        """Get schedule status (read-only)."""
        return {
            "schedules": [],
            "count": 0,
            "filter": {"plan_id": plan_id},
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
