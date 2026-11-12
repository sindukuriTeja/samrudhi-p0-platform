"""Kshamata — Agent Capacity (SAM-AG-067 · OPS-010).

Phase 3 operations agent. Manages capacity, tracks capacity usage, forecasts
capacity, and reports capacity status. Reports to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Kshamata(BaseAgent):
    """Agent Capacity."""

    canonical_id = "SAM-AG-067"
    name = "Kshamata"
    designation = "Agent Capacity"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.check_capacity": True,
        "ops.manage_capacity": True,
        "ops.track_capacity": True,
        "ops.forecast_capacity": True,
        "ops.report_capacity": True,
        "ops.escalate_capacity_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Kshamata, Agent Capacity (SAM-AG-067 · OPS-010) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-067 · Position: OPS-010
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Manage capacity, track capacity usage, forecast capacity needs, and report
capacity status. Every capacity decision has traceable metrics and rationale.

YOUR REGISTERS
1. Capacity Management Register — capacity allocations, agents, limits
2. Capacity Tracking Register — usage metrics, utilisation, trends
3. Capacity Forecast Register — forecasts, horizons, assumptions
4. Capacity Report Register — reports, periods, summaries
5. Capacity Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.manage_capacity · ops.track_capacity · ops.forecast_capacity
ops.report_capacity · ops.escalate_capacity_issue · gov.certify=False
gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate capacity data — missing data = "unavailable".
2. Never suppress a capacity constraint or overstate available capacity.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every capacity forecast has documented assumptions.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "manage")
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
                text=f"[MODEL UNAVAILABLE] {e}. Kshamata cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.capacity",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.manage_capacity")
    def manage_capacity(
        self,
        agent_id: str,
        capacity_units: int,
        resource_type: str,
    ) -> dict:
        """Manage capacity allocation for an agent."""
        capacity_id = f"CAP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "capacity_id": capacity_id,
            "agent_id": agent_id,
            "capacity_units": capacity_units,
            "resource_type": resource_type,
            "status": "managed",
            "managed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.track_capacity")
    def track_capacity(
        self,
        agent_id: str,
        used_units: int,
        total_units: int,
    ) -> dict:
        """Track capacity usage for an agent."""
        utilisation = used_units / total_units if total_units > 0 else 0.0
        return {
            "agent_id": agent_id,
            "used_units": used_units,
            "total_units": total_units,
            "utilisation": round(utilisation, 3),
            "status": "available" if utilisation < 0.7 else "busy" if utilisation < 0.9 else "saturated",
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.forecast_capacity")
    def forecast_capacity(
        self,
        agents: list,
        horizon_days: int,
        assumptions: dict,
    ) -> dict:
        """Forecast capacity needs for a horizon."""
        forecast_id = f"FCST-{uuid.uuid4().hex[:6].upper()}"
        return {
            "forecast_id": forecast_id,
            "agents": agents,
            "horizon_days": horizon_days,
            "assumptions": assumptions,
            "forecast": {a: {"projected_utilisation": 0.75} for a in agents},
            "forecasted_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.report_capacity")
    def report_capacity(
        self,
        period: str,
        agents: list,
        summary: dict,
    ) -> dict:
        """Generate a capacity report for a period."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "agents": agents,
            "summary": summary,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_capacity_issue")
    def escalate_capacity_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_agents: list,
    ) -> dict:
        """Escalate a capacity issue to human Board."""
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

    def list_capacity_allocations(
        self,
        agent_id: str | None = None,
        resource_type: str | None = None,
    ) -> dict:
        """List capacity allocations (read-only)."""
        return {
            "allocations": [],
            "count": 0,
            "filter": {"agent_id": agent_id, "resource_type": resource_type},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_capacity_status(
        self,
        agent_id: str | None = None,
    ) -> dict:
        """Get capacity status (read-only)."""
        return {
            "agents": [],
            "count": 0,
            "filter": {"agent_id": agent_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_forecasts(
        self,
        horizon_days: int | None = None,
    ) -> dict:
        """List capacity forecasts (read-only)."""
        return {
            "forecasts": [],
            "count": 0,
            "filter": {"horizon_days": horizon_days},
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

    @authority_guard("ops.check_capacity")
    def check_capacity(self, packages: list, routing: dict, max_per_agent: int = 10) -> dict:
        """Count the planned packages per producing agent (from routing) and warn when one is over its limit."""
        load = {}
        for p in packages or []:
            for agent in (routing or {}).get(p.get("type"), []):
                load[agent] = load.get(agent, 0) + 1
        over = {k: v for k, v in load.items() if v > max_per_agent}
        return {"load": load, "max_per_agent": max_per_agent, "overloaded": over,
                "status": "capacity_ok" if not over else "capacity_warning",
                "checked_at": datetime.now(timezone.utc).isoformat()}
