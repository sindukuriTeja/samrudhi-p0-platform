"""Sanskaran — Versioning and Release (SAM-AG-168).

Stage 1B service-first agent. Tracks versions, approvals and releases; supports rollback.
Service-first: version registry (Niyantrak owns agent_versions table; this is the service layer).
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Sanskaran(BaseAgent):
    """Versioning and Release."""

    canonical_id = "SAM-AG-168"
    name = "Sanskaran"
    designation = "Versioning and Release"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.tag_version": True,
        "tec.promote_release": True,
        "tec.rollback": True,
        "tec.list_versions": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._versions = {}

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "list")
        agent_id = kwargs.get("agent_id", "")
        if action == "tag":
            version = kwargs.get("version", "1.0.0")
            self._versions.setdefault(agent_id, []).append({
                "version": version, "status": "tagged",
                "at": datetime.now(timezone.utc).isoformat(),
            })
            text = f"Tagged {agent_id} @ {version}"
        elif action == "list":
            versions = self._versions.get(agent_id, [])
            text = f"Versions for {agent_id}:\n" + "\n".join(str(v) for v in versions) or "  (none)"
        elif action == "rollback":
            versions = self._versions.get(agent_id, [])
            if len(versions) >= 2:
                versions[-1]["status"] = "rolled_back"
                text = f"Rolled back {agent_id} from {versions[-1]['version']} to {versions[-2]['version']}"
            else:
                text = f"Cannot rollback {agent_id}: insufficient version history"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.tag_version")
    def tag(self, agent_id: str, version: str) -> dict:
        rec = {"version": version, "status": "tagged", "at": datetime.now(timezone.utc).isoformat()}
        self._versions.setdefault(agent_id, []).append(rec)
        return rec

    @authority_guard("tec.list_versions")
    def list_versions(self, agent_id: str) -> list:
        return self._versions.get(agent_id, [])

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
