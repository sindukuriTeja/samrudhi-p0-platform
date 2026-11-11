"""Pravahika — Workflow Runtime (SAM-AG-162).

Stage 1B service-first agent. Runs workflows step by step; retries failures; keeps state.
Service-first: deterministic workflow state machine.
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Pravahika(BaseAgent):
    """Workflow Runtime."""

    canonical_id = "SAM-AG-162"
    name = "Pravahika"
    designation = "Workflow Runtime"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.run_workflow": True,
        "tec.retry_step": True,
        "tec.get_state": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._workflows = {}

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "status")
        wf_id = kwargs.get("workflow_id", "")
        if action == "start":
            steps = kwargs.get("steps", [])
            self._workflows[wf_id] = {
                "status": "running", "steps": steps, "current": 0,
                "started": datetime.now(timezone.utc).isoformat(),
            }
            text = f"Workflow {wf_id} started with {len(steps)} steps"
        elif action == "advance":
            wf = self._workflows.get(wf_id)
            if wf:
                wf["current"] = min(wf["current"] + 1, len(wf["steps"]))
                wf["status"] = "completed" if wf["current"] >= len(wf["steps"]) else "running"
                text = f"Workflow {wf_id} advanced to step {wf['current']}, status={wf['status']}"
            else:
                text = f"Workflow {wf_id} not found"
                wf_id = ""
        elif action == "status":
            wf = self._workflows.get(wf_id)
            text = f"Workflow {wf_id} state: {wf}" if wf else f"Workflow {wf_id} not found"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.run_workflow")
    def start_workflow(self, workflow_id: str, steps: list) -> dict:
        record = {"status": "running", "steps": steps, "current": 0, "started": datetime.now(timezone.utc).isoformat()}
        self._workflows[workflow_id] = record
        return record

    @authority_guard("tec.get_state")
    def get_state(self, workflow_id: str) -> dict:
        return self._workflows.get(workflow_id, {"error": "not found"})
