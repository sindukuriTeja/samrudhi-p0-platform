"""Yantra — Agent Runtime Lead (SAM-AG-155).

Stage 1B service-first agent. Designs how agents run and hand work to each other.
Service-first: manages workflow runtime definitions and handoff rules.
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Yantra(BaseAgent):
    """Agent Runtime Lead."""

    canonical_id = "SAM-AG-155"
    name = "Yantra"
    designation = "Agent Runtime Lead"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.define_runtime": True,
        "tec.define_handoff": True,
        "tec.list_runtime": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._handoffs = {
            "arjun->sutra": {"trigger": "platform_change_request", "target": "SAM-AG-007"},
            "arjun->satya": {"trigger": "assurance_review", "target": "SAM-AG-010"},
            "arjun->niyantrak": {"trigger": "agent_lifecycle_action", "target": "SAM-AG-158"},
        }

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "list")
        if action == "list":
            text = "Runtime Handoff Rules:\n" + "\n".join(
                f"  - {k}: {v}" for k, v in self._handoffs.items()
            )
        elif action == "resolve":
            trigger = kwargs.get("trigger", "")
            matched = [k for k, v in self._handoffs.items() if v.get("trigger") == trigger]
            text = f"Trigger '{trigger}' routes to: {matched or 'no rule (escalate to human)'}"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.list_runtime")
    def list_handoffs(self) -> dict:
        return dict(self._handoffs)

    @authority_guard("tec.define_handoff")
    def resolve_handoff(self, trigger: str) -> dict:
        matched = {k: v for k, v in self._handoffs.items() if v.get("trigger") == trigger}
        return {"trigger": trigger, "routes": matched}
