"""Darpan — Dashboards & Visualisation (SAM-AG-126 · DAT-012).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Design and update dashboards and visualisations from validated KPI values; keep them
accurate and refreshed. [PDF 01A.08 · DAT-012 Dashboard & Visualisation]
Reports to Medha (AI CDO, SAM-AG-009).
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
class Darpan(BaseAgent):
    """Dashboards & Visualisation."""

    canonical_id = "SAM-AG-126"
    name = "Darpan"
    designation = "Dashboards & Visualisation"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.define_dashboard": True,
        "dat.refresh_dashboard": True,
        "dat.add_visualisation": True,
        "dat.check_dashboard_accuracy": True,
        "dat.escalate_dashboard_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "define_dashboard": "dat.define_dashboard",
        "refresh_dashboard": "dat.refresh_dashboard",
        "add_visualisation": "dat.add_visualisation",
        "check_dashboard_accuracy": "dat.check_dashboard_accuracy",
        "escalate_dashboard_issue": "dat.escalate_dashboard_issue",
    }

    SYSTEM_PROMPT = """You are Darpan, Dashboards & Visualisation (SAM-AG-126 · DAT-012) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-126 · Position: DAT-012 · Department: Analytics, Intelligence & Reporting
- You report to Medha (AI CDO, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Design and update dashboards and visualisations from validated KPI values; keep them accurate
and refreshed. [PDF 01A.08 · DAT-012 Dashboard & Visualisation]

YOUR REGISTERS
1. Dashboard Register — dashboard, audience, KPIs, refresh
2. Visualisation Register — chart, KPI, source

AUTHORITY MATRIX
dat.define_dashboard · dat.refresh_dashboard · dat.add_visualisation · dat.check_dashboard_accuracy · dat.escalate_dashboard_issue
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Show only validated KPI values; missing values are shown as unavailable.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "dashboard")
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
                text=f"[MODEL UNAVAILABLE] {e}. Darpan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="dat.dashboards",
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
    # Darpan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("dat.define_dashboard")
    def define_dashboard(self, name: str, kpis: list) -> dict:
        """Define a dashboard."""
        return {
            "record_id": f"DAR-{uuid.uuid4().hex[:6].upper()}",
            "name": name,
            "kpis": kpis,
            "action": "define_dashboard",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.refresh_dashboard")
    def refresh_dashboard(self, dashboard_id: str) -> dict:
        """Refresh a dashboard."""
        return {
            "record_id": f"DAR-{uuid.uuid4().hex[:6].upper()}",
            "dashboard_id": dashboard_id,
            "action": "refresh_dashboard",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.add_visualisation")
    def add_visualisation(self, dashboard_id: str, kpi: str, chart: str) -> dict:
        """Add a visualisation."""
        return {
            "record_id": f"DAR-{uuid.uuid4().hex[:6].upper()}",
            "dashboard_id": dashboard_id,
            "kpi": kpi,
            "chart": chart,
            "action": "add_visualisation",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.check_dashboard_accuracy")
    def check_dashboard_accuracy(self, dashboard_id: str) -> dict:
        """Check dashboard accuracy."""
        return {
            "record_id": f"DAR-{uuid.uuid4().hex[:6].upper()}",
            "dashboard_id": dashboard_id,
            "action": "check_dashboard_accuracy",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.escalate_dashboard_issue")
    def escalate_dashboard_issue(self, dashboard_id: str, issue: str) -> dict:
        """Escalate a dashboard issue."""
        return {
            "record_id": f"DAR-{uuid.uuid4().hex[:6].upper()}",
            "dashboard_id": dashboard_id,
            "issue": issue,
            "action": "escalate_dashboard_issue",
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
