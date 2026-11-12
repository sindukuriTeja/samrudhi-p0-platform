"""Pehchaan — Agent Identity and Registry (SAM-AG-159).

Stage 1B service-first agent. Creates and keeps each agent ID record and status.
Service-first: lightweight identity lookup service (uses the agents registry).
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent, load_all
from backend.core.authority import authority_guard


@register_agent
class Pehchaan(BaseAgent):
    """Agent Identity and Registry."""

    canonical_id = "SAM-AG-159"
    name = "Pehchaan"
    designation = "Agent Identity and Registry"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.lookup_agent": True,
        "tec.list_agents": True,
        "tec.register_agent": False,  # Niyantrak owns registration
        "ops.allocate": False,
    }

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "list")
        load_all()
        from agents.base import list_registered
        registered = list_registered()
        if action == "list":
            text = f"Registered agents ({len(registered)}):\n" + "\n".join(f"  - {cid}" for cid in registered)
        elif action == "lookup":
            cid = kwargs.get("canonical_id", "")
            text = f"Identity for {cid}: {'found' if cid in registered else 'not found'}"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.list_agents")
    def list_agents(self) -> list:
        load_all()
        from agents.base import list_registered
        return list_registered()

    @authority_guard("tec.lookup_agent")
    def lookup(self, canonical_id: str) -> dict:
        load_all()
        from agents.base import get_agent_class
        cls = get_agent_class(canonical_id)
        if cls is None:
            return {"canonical_id": canonical_id, "found": False}
        return {"canonical_id": canonical_id, "found": True, "name": cls.name, "type": cls.agent_type}

    def route_for_approval(
        self,
        request_type: str,
        details: dict,
    ) -> dict:
        """Route a request outside delegated authority to human approval."""
        import uuid as _uuid
        return {
            "request_id": f"REQ-{_uuid.uuid4().hex[:6].upper()}",
            "request_type": request_type,
            "details": details,
            "status": "pending_human_approval",
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }
