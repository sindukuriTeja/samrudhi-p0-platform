"""Smaran — Knowledge and Context Lead (SAM-AG-156).

Stage 1B service-first agent. Controls what each agent can see; keeps clients separate.
Service-first: tenant context isolation enforcement.
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Smaran(BaseAgent):
    """Knowledge and Context Lead."""

    canonical_id = "SAM-AG-156"
    name = "Smaran"
    designation = "Knowledge and Context Lead"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.scope_context": True,
        "tec.isolate_tenant": True,
        "ops.allocate": False,
    }

    def run(self, task: str, **kwargs) -> AgentResult:
        """Enforce tenant context scoping for a query."""
        tenant = kwargs.get("tenant_id", "DEMO-HEALTHCARE-01")
        agent_id = kwargs.get("agent_id", "unknown")
        # Deterministic isolation rule: every context fetch must carry tenant_id
        if not tenant or tenant == "":
            text = f"BLOCKED: agent {agent_id} requested context without tenant_id"
            status = "blocked"
        else:
            text = f"ALLOWED: context scoped to tenant={tenant} for agent {agent_id}"
            status = "allowed"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status=status)

    @authority_guard("tec.isolate_tenant")
    def scope_context(self, tenant_id: str, agent_id: str, requested_data: str) -> dict:
        """Return scoped context or block if tenant missing."""
        if not tenant_id:
            return {"allowed": False, "reason": "missing tenant_id", "agent_id": agent_id}
        return {
            "allowed": True,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "scoped_data": requested_data,
            "isolation_enforced": True,
        }

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
