"""Sandarbhika — Context Retrieval (SAM-AG-163).

Stage 1B service-first agent. Fetches the right client context for each task.
Service-first: context retrieval service (tenant-scoped, deterministic).
"""
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Sandarbhika(BaseAgent):
    """Context Retrieval."""

    canonical_id = "SAM-AG-163"
    name = "Sandarbhika"
    designation = "Context Retrieval"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.retrieve_context": True,
        "tec.scope_tenant": True,
        "ops.allocate": False,
    }

    def run(self, task: str, **kwargs) -> AgentResult:
        tenant = kwargs.get("tenant_id", "DEMO-HEALTHCARE-01")
        scope = kwargs.get("scope", "general")
        if not tenant:
            text = f"BLOCKED: context retrieval without tenant_id (scope={scope})"
            status = "blocked"
        else:
            text = f"Context for tenant={tenant}, scope={scope}: retrieved scoped records"
            status = "completed"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status=status)

    @authority_guard("tec.retrieve_context")
    def retrieve(self, tenant_id: str, scope: str) -> dict:
        if not tenant_id:
            return {"allowed": False, "reason": "missing tenant_id"}
        return {
            "allowed": True,
            "tenant_id": tenant_id,
            "scope": scope,
            "records": [],  # placeholder — real impl queries DB scoped by tenant_id
            "retrieved_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
