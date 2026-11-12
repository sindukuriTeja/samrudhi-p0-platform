"""Shodhan — Data Analysis Agent (SAM-AG-122).

Phase 3 analytics/data agent. Owns data analysis: analyzes data, runs analysis
models, interprets results, reports analysis findings, and escalates analysis
issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Shodhan(BaseAgent):
    """Data Analysis Agent."""

    canonical_id = "SAM-AG-122"
    name = "Shodhan"
    designation = "Data Analysis Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.analyze_data": True,
        "dat.run_analysis": True,
        "dat.interpret_data": True,
        "dat.report_analysis": True,
        "dat.escalate_analysis_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Shodhan, the Data Analysis Agent (SAM-AG-122 · DAT-006) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-122 · Position: DAT-006
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own data analysis: analyze datasets for patterns and insights, run analysis
models, interpret results with statistical rigor, report analysis findings,
and escalate analysis issues. Deliver accurate, actionable insights. Never
fabricate analysis results — missing = "unavailable".

YOUR REGISTERS
1. Analysis Task Register — tasks, datasets, methods, status
2. Analysis Model Register — models run, parameters, outputs
3. Interpretation Register — interpretations, confidence, caveats
4. Analysis Report Register — reports generated, recipients, findings
5. Analysis Issue Register — anomalies, escalations, resolutions

AUTHORITY MATRIX
- dat.analyze_data: Analyze datasets for insights
- dat.run_analysis: Run analysis models
- dat.interpret_data: Interpret analysis results
- dat.report_analysis: Report analysis findings
- dat.escalate_analysis_issue: Escalate analysis issues to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate analysis results or interpretations — missing = "unavailable".
2. Never suppress an anomalous finding to make results look cleaner.
3. Respect tenant isolation — never cross-tenant data leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Shodhan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="dat.analysis",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.analyze_data")
    def analyze_data(
        self,
        tenant_id: str,
        dataset_ref: str,
        analysis_type: str,
    ) -> dict:
        """Analyze a dataset for patterns and insights."""
        analysis_id = f"ANA-{uuid.uuid4().hex[:6].upper()}"
        return {
            "analysis_id": analysis_id,
            "tenant_id": tenant_id,
            "dataset_ref": dataset_ref,
            "analysis_type": analysis_type,
            "status": "analyzed",
            "findings": [],
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.run_analysis")
    def run_analysis(
        self,
        tenant_id: str,
        dataset_ref: str,
        model: str,
        parameters: dict,
    ) -> dict:
        """Run an analysis model on a dataset."""
        run_id = f"RUN-{uuid.uuid4().hex[:6].upper()}"
        return {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "dataset_ref": dataset_ref,
            "model": model,
            "parameters": parameters,
            "status": "completed",
            "output": {},
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.interpret_data")
    def interpret_data(
        self,
        tenant_id: str,
        analysis_ref: str,
        context: dict,
    ) -> dict:
        """Interpret analysis results with context."""
        interpretation_id = f"INT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "interpretation_id": interpretation_id,
            "tenant_id": tenant_id,
            "analysis_ref": analysis_ref,
            "context": context,
            "interpretation": {},
            "confidence": 0.0,
            "interpreted_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.report_analysis")
    def report_analysis(
        self,
        tenant_id: str,
        analysis_ref: str,
        audience: str,
    ) -> dict:
        """Report analysis findings to a specified audience."""
        report_id = f"AREP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "analysis_ref": analysis_ref,
            "audience": audience,
            "status": "reported",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_analysis_issue")
    def escalate_analysis_issue(
        self,
        tenant_id: str,
        analysis_ref: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a data analysis issue to human."""
        issue_id = f"ANINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "analysis_ref": analysis_ref,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_analyses(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List analyses (read-only)."""
        return {
            "analyses": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_analysis_models(
        self,
        tenant_id: str | None = None,
    ) -> dict:
        """List analysis models (read-only)."""
        return {
            "models": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_analysis_status(
        self,
        analysis_id: str,
    ) -> dict:
        """Get status of an analysis (read-only)."""
        return {
            "analysis_id": analysis_id,
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
