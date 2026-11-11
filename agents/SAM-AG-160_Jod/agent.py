"""Jod — MCP Connector Agent (SAM-AG-160).

Stage 1B service-first agent. Builds and configures connectors, APIs and webhooks.
Service-first: connector configuration store (stand-in for real MCP wiring).
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Jod(BaseAgent):
    """MCP Connector Agent."""

    canonical_id = "SAM-AG-160"
    name = "Jod"
    designation = "MCP Connector Agent"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.configure_connector": True,
        "tec.enable_connector": True,
        "tec.list_connectors": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._connectors = {}

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "list")
        if action == "list":
            text = "Configured connectors:\n" + "\n".join(
                f"  - {k}: {v['status']}" for k, v in self._connectors.items()
            ) or "  (none configured)"
        elif action == "configure":
            name = kwargs.get("name", "")
            endpoint = kwargs.get("endpoint", "")
            self._connectors[name] = {"status": "configured", "endpoint": endpoint, "at": datetime.now(timezone.utc).isoformat()}
            text = f"Connector {name} configured at {endpoint}"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.configure_connector")
    def configure(self, name: str, endpoint: str) -> dict:
        record = {"status": "configured", "endpoint": endpoint, "at": datetime.now(timezone.utc).isoformat()}
        self._connectors[name] = record
        return record

    @authority_guard("tec.list_connectors")
    def list_connectors(self) -> dict:
        return dict(self._connectors)
