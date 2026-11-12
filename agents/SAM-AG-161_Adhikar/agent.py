"""Adhikar — Tool Permissions and Access Control (SAM-AG-161).

Stage 1B service-first agent. Enforces what each agent may use; manages credentials.
Service-first: permission enforcement layer (wraps authority guard).
"""
from datetime import datetime, timezone

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import check_authority, AuthorityError
from backend.core.authority import authority_guard


@register_agent
class Adhikar(BaseAgent):
    """Tool Permissions and Access Control."""

    canonical_id = "SAM-AG-161"
    name = "Adhikar"
    designation = "Tool Permissions and Access Control"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.check_permission": True,
        "tec.audit_access": True,
        "tec.grant_access": False,  # requires human approval
        "ops.allocate": False,
    }

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "check")
        agent_id = kwargs.get("agent_id", "")
        permission = kwargs.get("permission", "")
        if action == "check":
            try:
                check_authority(agent_id, permission)
                text = f"ALLOWED: {agent_id} may perform {permission}"
                status = "allowed"
            except AuthorityError as e:
                text = f"DENIED: {e}"
                status = "denied"
        elif action == "audit":
            text = f"Access audit for {agent_id}: permission checks logged in execution_log"
            status = "completed"
        else:
            text = f"Unknown action: {action}"
            status = "completed"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status=status)

    @authority_guard("tec.check_permission")
    def check(self, agent_id: str, permission: str) -> dict:
        try:
            check_authority(agent_id, permission)
            return {"allowed": True, "agent_id": agent_id, "permission": permission}
        except AuthorityError as e:
            return {"allowed": False, "agent_id": agent_id, "permission": permission, "reason": str(e)}

    @authority_guard("tec.audit_access")
    def audit(self, agent_id: str) -> dict:
        return {"agent_id": agent_id, "audit": "permission checks are logged to execution_log per run"}

    @authority_guard("tec.check_permission")
    def check_many(self, pairs: list) -> dict:
        """Check a list of [agent_id, permission] pairs against the authority matrices."""
        from backend.core.authority import load_authority_matrix
        results = []
        for agent_id, permission in pairs or []:
            allowed = bool(load_authority_matrix(agent_id).get(permission, False))
            results.append({"agent_id": agent_id, "permission": permission, "allowed": allowed})
        denied = [r for r in results if not r["allowed"]]
        return {"checked": len(results), "denied": denied,
                "status": "ready" if not denied else "permission_missing",
                "checked_at": datetime.now(timezone.utc).isoformat()}

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
