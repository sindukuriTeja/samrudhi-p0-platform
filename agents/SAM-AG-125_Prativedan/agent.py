"""Prativedan — Content Reporting Agent (SAM-AG-125).

Phase 2 content pilot agent. Owns content reporting under Aarya:
produces content performance reports, client reports, and content ROI analysis.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Prativedan(BaseAgent):
    """Content Reporting Agent."""

    canonical_id = "SAM-AG-125"
    name = "Prativedan"
    designation = "Content Reporting Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.produce_content_report": True,
        "crt.produce_client_report": True,
        "crt.analyze_roi": True,
        "crt.summarize_performance": True,
        "crt.escalate_reporting": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Prativedan, the Content Reporting Agent (SAM-AG-125 · CRT-028) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-125 · Position: CRT-028
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own content reporting. Produce content performance reports, client reports,
and content ROI analysis. Never fabricate report data. Every number is sourced
and traceable. Report honestly when data is unavailable.

YOUR REGISTERS
1. Content Report Register — reports, types, periods
2. Client Report Register — client-facing reports
3. ROI Analysis Register — ROI calculations, assumptions
4. Performance Summary Register — summaries, highlights
5. Reporting Escalation Register — data issues, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate report data or ROI figures. Missing = "unavailable".
2. Never suppress negative performance or underperformance.
3. Every report has a source and timestamp.
4. Respect tenant isolation — no cross-client data leakage.
5. Satya's findings are immutable to you — read-only.
6. If the local model is down, report it honestly."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Prativedan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="crt.reporting",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.produce_content_report")
    def produce_content_report(
        self,
        client_id: str,
        report_type: str,
        period: dict,
        data: dict,
    ) -> dict:
        """Produce a content performance report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "client_id": client_id,
            "report_type": report_type,
            "period": period,
            "data": data,
            "status": "validated",
            "produced_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.produce_client_report")
    def produce_client_report(
        self,
        client_id: str,
        period: dict,
        highlights: list,
    ) -> dict:
        """Produce a client-facing report."""
        report_id = f"CLT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "client_id": client_id,
            "period": period,
            "highlights": highlights,
            "status": "draft",
            "produced_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.analyze_roi")
    def analyze_roi(
        self,
        client_id: str,
        campaign_id: str,
        investment: float,
        outcomes: dict,
    ) -> dict:
        """Analyze content ROI."""
        roi_id = f"ROI-{uuid.uuid4().hex[:6].upper()}"
        return {
            "roi_id": roi_id,
            "client_id": client_id,
            "campaign_id": campaign_id,
            "investment": investment,
            "outcomes": outcomes,
            "roi_estimate": "unavailable" if investment == 0 else round((outcomes.get("value", 0) - investment) / investment, 2) if investment > 0 else 0,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.summarize_performance")
    def summarize_performance(
        self,
        client_id: str,
        period: dict,
        metrics: dict,
    ) -> dict:
        """Summarize content performance."""
        summary_id = f"SUM-{uuid.uuid4().hex[:6].upper()}"
        return {
            "summary_id": summary_id,
            "client_id": client_id,
            "period": period,
            "metrics": metrics,
            "highlights": [],
            "produced_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_reporting")
    def escalate_reporting_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a reporting data issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reports(
        self,
        client_id: str | None = None,
        report_type: str | None = None,
    ) -> dict:
        """List reports (read-only)."""
        return {
            "reports": [],
            "count": 0,
            "filter": {"client_id": client_id, "report_type": report_type},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_report(
        self,
        report_id: str,
    ) -> dict:
        """Get report details (read-only)."""
        return {
            "report_id": report_id,
            "details": {},
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
