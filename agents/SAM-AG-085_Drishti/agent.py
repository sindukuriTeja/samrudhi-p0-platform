"""Drishti — Social Media Performance (SAM-AG-085).

Phase 2 content pilot agent. Owns social/content analytics under Aarya:
tracks content performance, engagement metrics, and produces analytics reports.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Drishti(BaseAgent):
    """Social Media Performance."""

    canonical_id = "SAM-AG-085"
    name = "Drishti"
    designation = "Social Media Performance"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.track_metrics": True,
        "crt.analyze_performance": True,
        "crt.produce_report": True,
        "crt.detect_trend": True,
        "crt.escalate_analytics": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Drishti, Social Media Performance (SAM-AG-085 · CRT-011) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-085 · Position: CRT-011
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own social and content analytics. Track content performance, engagement metrics,
and produce analytics reports. Never fabricate metrics. Every number is sourced
and traceable. Report honestly when data is unavailable.

YOUR REGISTERS
1. Metrics Register — raw metrics, sources, timestamps
2. Performance Register — content performance, KPIs
3. Analytics Report Register — reports, insights, recommendations
4. Trend Register — detected trends, patterns
5. Analytics Escalation Register — data issues, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate metrics or performance data. Missing = "unavailable".
2. Never suppress a negative trend or underperformance.
3. Every metric has a source and timestamp.
4. Respect tenant isolation — no cross-client data leakage.
5. Satya's findings are immutable to you — read-only.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "analyze")
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
                text=f"[MODEL UNAVAILABLE] {e}. Drishti cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.analytics",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.track_metrics")
    def track_metrics(
        self,
        client_id: str,
        content_ref: str,
        platform: str,
        metrics: dict,
    ) -> dict:
        """Track content metrics."""
        metric_id = f"MET-{uuid.uuid4().hex[:6].upper()}"
        return {
            "metric_id": metric_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "platform": platform,
            "metrics": metrics,
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.analyze_performance")
    def analyze_performance(
        self,
        client_id: str,
        content_refs: list,
        period: dict,
    ) -> dict:
        """Analyze content performance."""
        analysis_id = f"ANA-{uuid.uuid4().hex[:6].upper()}"
        return {
            "analysis_id": analysis_id,
            "client_id": client_id,
            "content_refs": content_refs,
            "period": period,
            "insights": {},
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.produce_report")
    def produce_analytics_report(
        self,
        client_id: str,
        report_type: str,
        period: dict,
        data: dict,
    ) -> dict:
        """Produce an analytics report."""
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

    @authority_guard("crt.detect_trend")
    def detect_trend(
        self,
        client_id: str,
        metric: str,
        data_points: list,
    ) -> dict:
        """Detect trends in metrics."""
        trend_id = f"TRD-{uuid.uuid4().hex[:6].upper()}"
        trend = "up" if len(data_points) > 1 and data_points[-1] > data_points[0] else "down" if len(data_points) > 1 and data_points[-1] < data_points[0] else "stable"
        return {
            "trend_id": trend_id,
            "client_id": client_id,
            "metric": metric,
            "trend": trend,
            "data_points": data_points,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_analytics")
    def escalate_analytics_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate an analytics data issue."""
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
        """List analytics reports (read-only)."""
        return {
            "reports": [],
            "count": 0,
            "filter": {"client_id": client_id, "report_type": report_type},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_metrics(
        self,
        client_id: str,
        content_ref: str | None = None,
    ) -> dict:
        """Get tracked metrics (read-only)."""
        return {
            "client_id": client_id,
            "content_ref": content_ref,
            "metrics": {},
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
