"""Vitaran — Resource Distribution Agent (SAM-AG-069 · OPS-008).

Phase 3 operations agent. Distributes resources, allocates resources,
balances load, and reports distribution status. Reports to Daksh
(SAM-AG-002, AI COO). NOTE: Spec file uses SAM-AG-066 but that conflicts
with Lakshya; this agent uses SAM-AG-069.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Vitaran(BaseAgent):
    """Resource Distribution Agent."""

    canonical_id = "SAM-AG-069"
    name = "Vitaran"
    designation = "Resource Distribution Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.distribute_resources": True,
        "ops.allocate_resources": True,
        "ops.balance_load": True,
        "ops.report_distribution": True,
        "ops.escalate_distribution_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Vitaran, the Resource Distribution Agent (SAM-AG-069 · OPS-008) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-069 · Position: OPS-008
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Distribute resources, allocate resources, balance load across agents, and
report distribution status. Every distribution has traceable allocation records.

YOUR REGISTERS
1. Distribution Register — distributions, sources, targets, quantities
2. Allocation Register — allocations, agents, resources, deadlines
3. Load Balancing Register — load metrics, balances, rebalancing actions
4. Distribution Report Register — reports, periods, summaries
5. Distribution Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.distribute_resources · ops.allocate_resources · ops.balance_load
ops.report_distribution · ops.escalate_distribution_issue · gov.certify=False
gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate distribution data — missing data = "unavailable".
2. Never suppress a load imbalance or overstate allocation capacity.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every distribution has source tracking and audit evidence.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "distribute")
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
                text=f"[MODEL UNAVAILABLE] {e}. Vitaran cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.distribute",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.distribute_resources")
    def distribute_resources(
        self,
        resource_type: str,
        targets: list,
        quantities: dict,
    ) -> dict:
        """Distribute resources to targets."""
        distribution_id = f"DIST-{uuid.uuid4().hex[:6].upper()}"
        return {
            "distribution_id": distribution_id,
            "resource_type": resource_type,
            "targets": targets,
            "quantities": quantities,
            "status": "distributed",
            "distributed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.allocate_resources")
    def allocate_resources(
        self,
        agent_id: str,
        resource_type: str,
        quantity: int,
        deadline: str,
    ) -> dict:
        """Allocate resources to an agent."""
        allocation_id = f"ALLOC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "allocation_id": allocation_id,
            "agent_id": agent_id,
            "resource_type": resource_type,
            "quantity": quantity,
            "deadline": deadline,
            "status": "allocated",
            "allocated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.balance_load")
    def balance_load(
        self,
        agents: list,
        current_load: dict,
    ) -> dict:
        """Balance load across agents."""
        rebalanced = {a: "balanced" for a in agents}
        return {
            "agents": agents,
            "current_load": current_load,
            "rebalanced": rebalanced,
            "status": "balanced",
            "balanced_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.report_distribution")
    def report_distribution(
        self,
        period: str,
        distributions: list,
        summary: dict,
    ) -> dict:
        """Generate a distribution report for a period."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "distributions": distributions,
            "summary": summary,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_distribution_issue")
    def escalate_distribution_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_agents: list,
    ) -> dict:
        """Escalate a distribution issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_agents": affected_agents,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_distributions(
        self,
        resource_type: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List distribution records (read-only)."""
        return {
            "distributions": [],
            "count": 0,
            "filter": {"resource_type": resource_type, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_load_status(
        self,
        agent_id: str | None = None,
    ) -> dict:
        """Get load status for agents (read-only)."""
        return {
            "agents": [],
            "count": 0,
            "filter": {"agent_id": agent_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_allocations(
        self,
        agent_id: str | None = None,
        resource_type: str | None = None,
    ) -> dict:
        """List resource allocations (read-only)."""
        return {
            "allocations": [],
            "count": 0,
            "filter": {"agent_id": agent_id, "resource_type": resource_type},
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
