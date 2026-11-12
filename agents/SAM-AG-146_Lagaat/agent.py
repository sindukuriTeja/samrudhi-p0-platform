"""Lagaat — AI Workforce & Service Costing (SAM-AG-146 · FIN-014).

Stage 2 Phase 2 content-pilot agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Work out service costs: AI execution cost per run, cost per accepted deliverable, and
vendor and subscription costs, from the run log and approved rates. [PDF 01A.09 ·
FIN-014 Service Costing & AI Workforce Economics; processes FIN-P26, FIN-P27]
Reports to Niti (AI CFO, SAM-AG-006; not yet deployed, route to the human finance owner).
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
class Lagaat(BaseAgent):
    """AI Workforce & Service Costing."""

    canonical_id = "SAM-AG-146"
    name = "Lagaat"
    designation = "AI Workforce & Service Costing"
    agent_type = "thinking"

    AUTHORITY = {
        "fin.summarise_run_cost": True,
        "fin.compute_cost_per_deliverable": True,
        "fin.attribute_run_cost": True,
        "fin.record_vendor_cost": True,
        "fin.report_service_cost": True,
        "fin.escalate_cost_overrun": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "summarise_run_cost": "fin.summarise_run_cost",
        "compute_cost_per_deliverable": "fin.compute_cost_per_deliverable",
        "attribute_run_cost": "fin.attribute_run_cost",
        "record_vendor_cost": "fin.record_vendor_cost",
        "report_service_cost": "fin.report_service_cost",
        "escalate_cost_overrun": "fin.escalate_cost_overrun",
    }

    SYSTEM_PROMPT = """You are Lagaat, AI Workforce & Service Costing (SAM-AG-146 · FIN-014) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-146 · Position: FIN-014 · Department: Finance & Administration
- You report to Niti (AI CFO, SAM-AG-006; not yet deployed, route to the human finance owner).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Work out service costs: AI execution cost per run, cost per accepted deliverable, and vendor and
subscription costs, from the run log and approved rates. [PDF 01A.09 · FIN-014 Service Costing &
AI Workforce Economics; processes FIN-P26, FIN-P27]

YOUR REGISTERS
1. Service Cost Register — client, period, cost, accepted deliverables
2. Run Cost Register — execution, tokens, cost
3. Vendor Cost Register — vendor, subscription, cost

AUTHORITY MATRIX
fin.summarise_run_cost · fin.compute_cost_per_deliverable · fin.attribute_run_cost · fin.record_vendor_cost · fin.report_service_cost · fin.escalate_cost_overrun
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Numbers are computed in code from the run log; never estimate a cost the data does not support.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "cost")
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
                text=f"[MODEL UNAVAILABLE] {e}. Lagaat cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="fin.costing",
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
    # Lagaat's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("fin.summarise_run_cost")
    def summarise_run_cost(self, tokens: int, steps: int, accepted_deliverables: int, cost_per_1k_tokens: float = None) -> dict:
        """Summarise model usage and cost for a project."""
        if cost_per_1k_tokens is None:
            cost, note = None, "No cost rate configured (project_flows.yaml defaults.cost_per_1k_tokens); cost unavailable."
        else:
            cost, note = round(tokens / 1000.0 * float(cost_per_1k_tokens), 4), "Model cost only; human review time not included."
        per = round(cost / accepted_deliverables, 4) if cost is not None and accepted_deliverables > 0 else None
        return {
            "model_steps": steps,
            "tokens": tokens,
            "accepted_deliverables": accepted_deliverables,
            "total_cost": cost if cost is not None else "unavailable",
            "cost_per_accepted_deliverable": per if per is not None else "unavailable",
            "note": note,
            "status": "computed" if per is not None else "partial",
            "computed_at": _now(),
        }

    @authority_guard("fin.compute_cost_per_deliverable")
    def compute_cost_per_deliverable(self, total_cost: float, accepted_deliverables: int) -> dict:
        """Cost per accepted deliverable."""
        if accepted_deliverables <= 0:
            return {"status": "unavailable", "reason": "no accepted deliverables", "computed_at": _now()}
        return {
            "total_cost": round(float(total_cost), 2),
            "accepted_deliverables": accepted_deliverables,
            "cost_per_accepted_deliverable": round(float(total_cost) / accepted_deliverables, 2),
            "status": "computed",
            "computed_at": _now(),
        }

    @authority_guard("fin.attribute_run_cost")
    def attribute_run_cost(self, tokens: int, cost_per_1k_tokens: float, human_minutes: float = 0.0, human_rate_per_hour: float = 0.0) -> dict:
        """Cost of one run."""
        ai_cost = tokens / 1000.0 * cost_per_1k_tokens
        human_cost = human_minutes / 60.0 * human_rate_per_hour
        return {
            "tokens": tokens,
            "ai_cost": round(ai_cost, 4),
            "human_cost": round(human_cost, 2),
            "total_cost": round(ai_cost + human_cost, 4),
            "status": "computed",
            "computed_at": _now(),
        }

    @authority_guard("fin.record_vendor_cost")
    def record_vendor_cost(self, vendor: str, monthly_cost: float) -> dict:
        """Record a vendor cost."""
        return {
            "record_id": f"LAG-{uuid.uuid4().hex[:6].upper()}",
            "vendor": vendor,
            "monthly_cost": monthly_cost,
            "action": "record_vendor_cost",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("fin.report_service_cost")
    def report_service_cost(self, client_id: str, period: str) -> dict:
        """Report service cost for a period."""
        return {
            "record_id": f"LAG-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "period": period,
            "action": "report_service_cost",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("fin.escalate_cost_overrun")
    def escalate_cost_overrun(self, client_id: str, overrun: float) -> dict:
        """Escalate a cost overrun."""
        return {
            "record_id": f"LAG-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "overrun": overrun,
            "action": "escalate_cost_overrun",
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
