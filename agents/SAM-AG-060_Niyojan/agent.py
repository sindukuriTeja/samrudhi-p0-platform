"""Niyojan — Resource & Capacity Lead (SAM-AG-060 · OPS-003).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Decide which resources a plan needs, set allocation policies, govern utilisation and
balance workload across agents and human reviewers. [PDF 01A.05 · OPS-003 Resource &
Capacity Management Lead]
Reports to Daksh (AI COO, SAM-AG-002).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Niyojan(BaseAgent):
    """Resource & Capacity Lead."""

    canonical_id = "SAM-AG-060"
    name = "Niyojan"
    designation = "Resource & Capacity Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.assess_resource_need": True,
        "ops.set_allocation_policy": True,
        "ops.review_utilisation": True,
        "ops.balance_workload": True,
        "ops.escalate_capacity_gap": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "assess_resource_need": "ops.assess_resource_need",
        "set_allocation_policy": "ops.set_allocation_policy",
        "review_utilisation": "ops.review_utilisation",
        "balance_workload": "ops.balance_workload",
        "escalate_capacity_gap": "ops.escalate_capacity_gap",
    }

    SYSTEM_PROMPT = """You are Niyojan, Resource & Capacity Lead (SAM-AG-060 · OPS-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-060 · Position: OPS-003 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Decide which resources a plan needs, set allocation policies, govern utilisation and balance
workload across agents and human reviewers. [PDF 01A.05 · OPS-003 Resource & Capacity Management
Lead]

YOUR REGISTERS
1. Resource Need Register — plan, resource, quantity, period
2. Allocation Policy Register — policy, scope, version
3. Utilisation Register — agent, period, utilisation

AUTHORITY MATRIX
ops.assess_resource_need · ops.set_allocation_policy · ops.review_utilisation · ops.balance_workload · ops.escalate_capacity_gap
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never overload an agent or reviewer beyond approved capacity.
5. If the local model is down, report it honestly — do not fake output."""

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
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500], format=kwargs.get("output_format")))
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
                event_type="ops.resources",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    # ------------------------------------------------------------------
    # Niyojan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.assess_resource_need")
    def assess_resource_need(self, plan_id: str, packages: list) -> dict:
        """Assess resources a plan needs."""
        return {
            "record_id": f"NIY-{uuid.uuid4().hex[:6].upper()}",
            "plan_id": plan_id,
            "packages": packages,
            "action": "assess_resource_need",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.set_allocation_policy")
    def set_allocation_policy(self, policy: str, scope: str) -> dict:
        """Set an allocation policy."""
        return {
            "record_id": f"NIY-{uuid.uuid4().hex[:6].upper()}",
            "policy": policy,
            "scope": scope,
            "action": "set_allocation_policy",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.review_utilisation")
    def review_utilisation(self, period: str) -> dict:
        """Review utilisation for a period."""
        return {
            "record_id": f"NIY-{uuid.uuid4().hex[:6].upper()}",
            "period": period,
            "action": "review_utilisation",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.balance_workload")
    def balance_workload(self, agents: list) -> dict:
        """Balance workload across agents."""
        return {
            "record_id": f"NIY-{uuid.uuid4().hex[:6].upper()}",
            "agents": agents,
            "action": "balance_workload",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_capacity_gap")
    def escalate_capacity_gap(self, plan_id: str, gap: str) -> dict:
        """Escalate a capacity gap."""
        return {
            "record_id": f"NIY-{uuid.uuid4().hex[:6].upper()}",
            "plan_id": plan_id,
            "gap": gap,
            "action": "escalate_capacity_gap",
            "status": "recorded",
            "recorded_at": _now(),
        }

    # ------------------------------------------------------------------
    # Read-only and escalation
    # ------------------------------------------------------------------

    def list_records(self, register: str | None = None) -> dict:
        """List register records (read-only)."""
        return {
            "records": [],
            "count": 0,
            "filter": {"register": register},
            "queried_at": _now(),
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
            "routed_at": _now(),
        }
