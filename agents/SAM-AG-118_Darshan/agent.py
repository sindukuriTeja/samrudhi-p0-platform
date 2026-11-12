"""Darshan — BI & Reporting Lead (SAM-AG-118).

Phase 3 analytics/data agent. Owns business intelligence and reporting:
generates BI reports, schedules reports, publishes reports, and escalates
reporting issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Darshan(BaseAgent):
    """BI & Reporting Lead."""

    canonical_id = "SAM-AG-118"
    name = "Darshan"
    designation = "BI & Reporting Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.bi_report": True,
        "dat.generate_report": True,
        "dat.schedule_report": True,
        "dat.publish_report": True,
        "dat.escalate_reporting_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Darshan, BI & Reporting Lead (SAM-AG-118 · DAT-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-118 · Position: DAT-004
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own business intelligence and reporting: generate BI reports, schedule recurring
reports, publish reports to stakeholders, and escalate reporting issues. Deliver
actionable insights through clear, accurate reports. Never fabricate report data
— missing = "unavailable".

YOUR REGISTERS
1. BI Report Register — report definitions, templates, parameters
2. Generated Report Register — produced reports, timestamps, recipients
3. Schedule Register — recurring report schedules, cadence, next run
4. Publication Register — published reports, distribution lists, access
5. Reporting Issue Register — failures, escalations, resolutions

AUTHORITY MATRIX
- dat.bi_report: Generate business intelligence reports
- dat.generate_report: Generate ad-hoc reports
- dat.schedule_report: Schedule recurring reports
- dat.publish_report: Publish reports to stakeholders
- dat.escalate_reporting_issue: Escalate reporting failures to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate report data or metrics — missing = "unavailable".
2. Never suppress a reporting failure to avoid escalation.
3. Respect tenant isolation — never cross-tenant report leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "generate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Darshan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="dat.reporting",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.bi_report")
    def generate_bi_report(
        self,
        tenant_id: str,
        report_type: str,
        parameters: dict,
    ) -> dict:
        """Generate a business intelligence report."""
        report_id = f"BI-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "report_type": report_type,
            "parameters": parameters,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.generate_report")
    def generate_report(
        self,
        tenant_id: str,
        report_name: str,
        data_sources: list,
    ) -> dict:
        """Generate an ad-hoc report from specified data sources."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "report_name": report_name,
            "data_sources": data_sources,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.schedule_report")
    def schedule_report(
        self,
        tenant_id: str,
        report_ref: str,
        cadence: str,
        recipients: list,
    ) -> dict:
        """Schedule a recurring report."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "tenant_id": tenant_id,
            "report_ref": report_ref,
            "cadence": cadence,
            "recipients": recipients,
            "status": "scheduled",
            "next_run": None,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.publish_report")
    def publish_report(
        self,
        tenant_id: str,
        report_id: str,
        distribution_list: list,
    ) -> dict:
        """Publish a report to stakeholders."""
        publication_id = f"PUB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "publication_id": publication_id,
            "tenant_id": tenant_id,
            "report_id": report_id,
            "distribution_list": distribution_list,
            "status": "published",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_reporting_issue")
    def escalate_reporting_issue(
        self,
        tenant_id: str,
        report_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a reporting issue to human."""
        issue_id = f"RPTINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "report_id": report_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reports(
        self,
        tenant_id: str | None = None,
        report_type: str | None = None,
    ) -> dict:
        """List reports (read-only)."""
        return {
            "reports": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "report_type": report_type},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_schedules(
        self,
        tenant_id: str | None = None,
    ) -> dict:
        """List report schedules (read-only)."""
        return {
            "schedules": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_report_status(
        self,
        report_id: str,
    ) -> dict:
        """Get status of a report (read-only)."""
        return {
            "report_id": report_id,
            "status": "unknown",
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
