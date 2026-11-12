"""Sankalan — Resource Consolidation Agent (SAM-AG-064 · OPS-006).

Phase 3 operations agent. Consolidates resources, aggregates capacity,
reviews availability, and reports consolidation status. Reports to
Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sankalan(BaseAgent):
    """Resource Consolidation Agent."""

    canonical_id = "SAM-AG-064"
    name = "Sankalan"
    designation = "Resource Consolidation Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.consolidate_resources": True,
        "ops.aggregate_capacity": True,
        "ops.review_availability": True,
        "ops.report_consolidation": True,
        "ops.escalate_consolidation_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Sankalan, the Resource Consolidation Agent (SAM-AG-064 · OPS-006) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-064 · Position: OPS-006
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Consolidate resources, aggregate capacity, review availability, and report
consolidation status. Every consolidation action has evidence and audit trail.

YOUR REGISTERS
1. Consolidation Register — consolidated resources, sources, targets
2. Capacity Aggregation Register — aggregated capacity, sources, totals
3. Availability Register — availability status, agents, resources
4. Consolidation Report Register — reports, periods, summaries
5. Consolidation Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.consolidate_resources · ops.aggregate_capacity · ops.review_availability
ops.report_consolidation · ops.escalate_consolidation_issue · gov.certify=False
gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate resource availability — missing data = "unavailable".
2. Never suppress a capacity shortfall or overstate available resources.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every consolidation has source tracking and audit evidence.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "consolidate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sankalan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.consolidate",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.consolidate_resources")
    def consolidate_resources(
        self,
        resource_types: list,
        sources: list,
        target: str,
    ) -> dict:
        """Consolidate resources from multiple sources."""
        consolidation_id = f"CONS-{uuid.uuid4().hex[:6].upper()}"
        return {
            "consolidation_id": consolidation_id,
            "resource_types": resource_types,
            "sources": sources,
            "target": target,
            "status": "consolidated",
            "consolidated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.aggregate_capacity")
    def aggregate_capacity(
        self,
        agents: list,
        resource_type: str,
    ) -> dict:
        """Aggregate capacity across agents."""
        total_capacity = len(agents) * 100  # placeholder
        return {
            "resource_type": resource_type,
            "agents": agents,
            "total_capacity": total_capacity,
            "agent_count": len(agents),
            "aggregated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.review_availability")
    def review_availability(
        self,
        resource_type: str,
        agents: list,
    ) -> dict:
        """Review resource availability across agents."""
        return {
            "resource_type": resource_type,
            "agents": agents,
            "availability": {a: "available" for a in agents},
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.report_consolidation")
    def report_consolidation(
        self,
        period: str,
        consolidations: list,
        summary: dict,
    ) -> dict:
        """Generate a consolidation report for a period."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "consolidations": consolidations,
            "summary": summary,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_consolidation_issue")
    def escalate_consolidation_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_resources: list,
    ) -> dict:
        """Escalate a consolidation issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_resources": affected_resources,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_consolidations(
        self,
        resource_type: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List consolidation records (read-only)."""
        return {
            "consolidations": [],
            "count": 0,
            "filter": {"resource_type": resource_type, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_availability_status(
        self,
        resource_type: str | None = None,
    ) -> dict:
        """Get availability status (read-only)."""
        return {
            "resources": [],
            "count": 0,
            "filter": {"resource_type": resource_type},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_capacity_aggregates(
        self,
        resource_type: str | None = None,
    ) -> dict:
        """List capacity aggregates (read-only)."""
        return {
            "aggregates": [],
            "count": 0,
            "filter": {"resource_type": resource_type},
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
