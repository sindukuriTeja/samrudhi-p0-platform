"""Lakshya — Enterprise KPI Intelligence Agent (SAM-AG-066).

Phase 3 CEO Office agent. Owns enterprise KPI measurement, performance tracking,
and executive reporting. Provides data-driven intelligence to the CEO (Arjun).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Lakshya(BaseAgent):
    """Enterprise KPI Intelligence Agent."""

    canonical_id = "SAM-AG-066"
    name = "Lakshya"
    designation = "Enterprise KPI Intelligence Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ceo.measure_kpi": True,
        "ceo.track_enterprise_metrics": True,
        "ceo.analyze_performance": True,
        "ceo.report_kpi": True,
        "ceo.escalate_kpi_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Lakshya, the Enterprise KPI Intelligence Agent (SAM-AG-066 · CEO-003) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-066 · Position: CEO-003 · Legacy: SAM-EX-066
- You report to Arjun (AI CEO, SAM-AG-001). You do NOT report to any other agent.
- You own enterprise KPI measurement, performance tracking, and executive reporting.
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Measure, track, and report enterprise KPIs across all business units. Provide
data-driven performance intelligence to the CEO. Never fabricate metrics —
missing data = "unavailable". Never suppress a declining KPI to improve the score.

YOUR FIVE REGISTERS
1. KPI Registry — defined KPIs, targets, thresholds, owners
2. Enterprise Metrics Register — actual values, trends, periods
3. Performance Analysis Register — variance analysis, root causes, insights
4. KPI Report Register — generated reports, recipients, periods
5. KPI Escalation Register — threshold breaches, escalations, actions

HARD RULES — NEVER VIOLATE
1. Never fabricate KPI data or performance metrics. Missing = "unavailable".
2. Never suppress a declining KPI or threshold breach to improve the score.
3. Never change approved KPI targets or thresholds — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every KPI has a target, actual, variance, and owner.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "measure")
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
                text=f"[MODEL UNAVAILABLE] {e}. Lakshya cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ceo.kpi",
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
    # Lakshya's 5 domain tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ceo.measure_kpi")
    def measure_kpi(
        self,
        kpi_id: str,
        actual_value: float | None,
        period: str,
        unit: str = "raw",
    ) -> dict:
        """Measure a KPI value for a given period."""
        measurement_id = f"MEAS-{uuid.uuid4().hex[:6].upper()}"
        return {
            "measurement_id": measurement_id,
            "kpi_id": kpi_id,
            "actual_value": actual_value,
            "period": period,
            "unit": unit,
            "status": "measured",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "measured_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.track_enterprise_metrics")
    def track_enterprise_metrics(
        self,
        business_unit: str,
        metrics: dict,
        period: str,
    ) -> dict:
        """Track enterprise metrics across business units."""
        tracking_id = f"TRK-{uuid.uuid4().hex[:6].upper()}"
        return {
            "tracking_id": tracking_id,
            "business_unit": business_unit,
            "metrics": metrics,
            "period": period,
            "metric_count": len(metrics),
            "status": "tracked",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.analyze_performance")
    def analyze_performance(
        self,
        kpi_id: str,
        actual: float | None,
        target: float,
        period: str,
    ) -> dict:
        """Analyze performance variance for a KPI."""
        analysis_id = f"ANL-{uuid.uuid4().hex[:6].upper()}"
        variance = None
        if actual is not None:
            variance = actual - target
            variance_pct = (variance / abs(target) * 100) if target != 0 else None
        else:
            variance_pct = None
        status = "unavailable" if actual is None else ("on_target" if (variance is not None and variance >= 0) else "below_target")
        return {
            "analysis_id": analysis_id,
            "kpi_id": kpi_id,
            "actual": actual,
            "target": target,
            "variance": variance,
            "variance_pct": variance_pct,
            "period": period,
            "status": status,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.report_kpi")
    def generate_kpi_report(
        self,
        period: str,
        kpis: list,
        business_units: list,
    ) -> dict:
        """Generate a KPI performance report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "kpis_count": len(kpis),
            "business_units_count": len(business_units),
            "status": "generated",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ceo.escalate_kpi_issue")
    def escalate_kpi_issue(
        self,
        kpi_id: str,
        severity: str,
        description: str,
        affected_units: list,
    ) -> dict:
        """Escalate a KPI threshold breach or performance issue to human."""
        escalation_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "escalation_id": escalation_id,
            "kpi_id": kpi_id,
            "severity": severity,  # S1..S4
            "description": description,
            "affected_units": affected_units,
            "status": "escalated",
            "tenant_id": "DEMO-HEALTHCARE-01",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Read-only methods (no authority guard needed)
    # ------------------------------------------------------------------

    def list_kpis(
        self,
        business_unit: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List defined KPIs (read-only)."""
        return {
            "kpis": [],
            "count": 0,
            "filter": {"business_unit": business_unit, "status": status},
            "tenant_id": "DEMO-HEALTHCARE-01",
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_kpi_measurements(
        self,
        kpi_id: str,
        period: str | None = None,
    ) -> dict:
        """Get KPI measurement history (read-only)."""
        return {
            "kpi_id": kpi_id,
            "measurements": [],
            "count": 0,
            "filter": {"period": period},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_performance_summary(
        self,
        business_unit: str | None = None,
        period: str | None = None,
    ) -> dict:
        """Get performance summary (read-only)."""
        return {
            "business_unit": business_unit,
            "period": period,
            "kpis": [],
            "count": 0,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_escalations(
        self,
        status: str | None = None,
    ) -> dict:
        """List KPI escalations (read-only)."""
        return {
            "escalations": [],
            "count": 0,
            "filter": {"status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Route for approval (outside delegated authority)
    # ------------------------------------------------------------------

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
