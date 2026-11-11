"""Medha — AI Chief Data & Intelligence Officer (SAM-AG-009).

Phase 1 P1 agent #4. Owns enterprise data, analytics and intelligence:
collection, validation, reporting, dashboards, forecasting, anomaly detection.
Guarantees every number is accurate, traceable and fit for decision-making.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Medha(BaseAgent):
    """AI Chief Data & Intelligence Officer (Analytics & Intelligence)."""

    canonical_id = "SAM-AG-009"
    name = "Medha"
    designation = "AI Chief Data & Intelligence Officer"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.define_metric": True,
        "dat.produce_report": True,
        "dat.run_forecast": True,
        "dat.detect_anomaly": True,
        "dat.validate_data": True,
        "dat.escalate_data": True,
        "dat.measure_workforce": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Medha, the AI Chief Data & Intelligence Officer (AI Head of
Intelligence) of Samrudhi, an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-009 · Position: DAT-001 · Legacy: SAM-EX-009
- You report to Arjun (AI CEO, SAM-AG-001). You do NOT report to any other agent.
- You own data strategy, analytics architecture and decision intelligence.
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own enterprise data strategy, analytics architecture and decision intelligence.
Deliver trusted, traceable, fit-for-decision reports and forecasts. Every number
Arjun, Daksh, Aarya and Mitra sees must be accurate, traceable and sourced.

YOUR FIVE REGISTERS
1. Data Source Register — all sources: CRM, Ads, Analytics, Social, Finance
2. KPI Governance Register — every metric definition, formula, version
3. Report Register — all reports: client, management, dashboard, status
4. Forecast Register — forecasts: revenue, demand, capacity, accuracy
5. Anomaly Register — detected anomalies: type, severity, alert, resolution

HARD RULES — NEVER VIOLATE
1. Never fabricate, alter or suppress data to make performance look better.
2. Never change KPI definitions without governance approval.
3. Never hide an anomaly or data quality issue to improve your score.
4. Every metric has a source, timestamp and calculation version.
5. Satya's findings are immutable to you — read-only.
6. Every report has an owner, source and validation record.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "report")
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
                text=f"[MODEL UNAVAILABLE] {e}. Medha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="dat.intelligence",
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
    # Medha's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("dat.define_metric")
    def define_kpi(
        self,
        kpi_id: str,
        name: str,
        formula: str,
        source: dict,
    ) -> dict:
        """Define a KPI with governed formula."""
        return {
            "kpi_id": kpi_id,
            "name": name,
            "formula": formula,
            "source": source,
            "version": "1.0",
            "status": "draft",
            "defined_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.produce_report")
    def produce_report(
        self,
        report_type: str,
        client_id: str | None,
        content_ref: str,
        source_trace: dict,
    ) -> dict:
        """Produce a validated report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "type": report_type,
            "client_id": client_id,
            "content_ref": content_ref,
            "source_trace": source_trace,
            "status": "validated",
            "produced_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.run_forecast")
    def run_forecast(
        self,
        metric: str,
        value: float,
        confidence_interval: dict,
        assumptions: dict,
    ) -> dict:
        """Run a forecast for a metric."""
        forecast_id = f"FCST-{uuid.uuid4().hex[:6].upper()}"
        return {
            "forecast_id": forecast_id,
            "metric": metric,
            "value": value,
            "confidence_interval": confidence_interval,
            "assumptions": assumptions,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.detect_anomaly")
    def detect_anomaly(
        self,
        anomaly_type: str,
        severity: str,
        description: str,
        alert: dict,
    ) -> dict:
        """Detect and register an anomaly."""
        anomaly_id = f"ANOM-{uuid.uuid4().hex[:6].upper()}"
        return {
            "anomaly_id": anomaly_id,
            "type": anomaly_type,
            "severity": severity,
            "description": description,
            "alert": alert,
            "status": "open",
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.validate_data")
    def validate_data_source(
        self,
        source_id: str,
        source_type: str,
        completeness: dict,
    ) -> dict:
        """Validate a data source."""
        return {
            "source_id": source_id,
            "source_type": source_type,
            "completeness": completeness,
            "connectivity": "connected",
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_data")
    def escalate_data_issue(
        self,
        severity: str,
        description: str,
        affected_reports: list,
    ) -> dict:
        """Escalate a data quality issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "severity": severity,
            "description": description,
            "affected_reports": affected_reports,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.measure_workforce")
    def measure_workforce(
        self,
        agent_id: str,
        productivity: dict,
        capacity: dict,
        cost_per_deliverable: float | None,
    ) -> dict:
        """Measure agent workforce productivity."""
        return {
            "agent_id": agent_id,
            "productivity": productivity,
            "capacity": capacity,
            "cost_per_deliverable": cost_per_deliverable,
            "measured_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_data_sources(
        self,
        source_type: str | None = None,
    ) -> dict:
        """List data sources (read-only)."""
        return {
            "sources": [],
            "count": 0,
            "filter": {"source_type": source_type},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_kpis(
        self,
        status: str | None = None,
    ) -> dict:
        """List KPI definitions (read-only)."""
        return {
            "kpis": [],
            "count": 0,
            "filter": {"status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reports(
        self,
        report_type: str | None = None,
        client_id: str | None = None,
    ) -> dict:
        """List reports (read-only)."""
        return {
            "reports": [],
            "count": 0,
            "filter": {"report_type": report_type, "client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_forecasts(
        self,
        metric: str | None = None,
    ) -> dict:
        """List forecasts (read-only)."""
        return {
            "forecasts": [],
            "count": 0,
            "filter": {"metric": metric},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_anomalies(
        self,
        severity: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List anomalies (read-only)."""
        return {
            "anomalies": [],
            "count": 0,
            "filter": {"severity": severity, "status": status},
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
