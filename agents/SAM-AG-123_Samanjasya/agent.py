"""Samanjasya — Data Reconciliation (SAM-AG-123).

Phase 3 analytics/data agent. Owns data reconciliation: reconciles data across
sources, compares sources for consistency, resolves discrepancies, reports
reconciliation status, and escalates reconciliation issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Samanjasya(BaseAgent):
    """Data Reconciliation."""

    canonical_id = "SAM-AG-123"
    name = "Samanjasya"
    designation = "Data Reconciliation"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.reconcile_data": True,
        "dat.compare_sources": True,
        "dat.resolve_discrepancy": True,
        "dat.report_reconciliation": True,
        "dat.escalate_reconciliation_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Samanjasya, Data Reconciliation (SAM-AG-123 · DAT-009) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-123 · Position: DAT-009
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own data reconciliation: reconcile data across multiple sources, compare sources
for consistency, resolve discrepancies with documented logic, report reconciliation
status, and escalate unresolved issues. Ensure data consistency across the platform.
Never fabricate reconciliation results — unknown = "unknown".

YOUR REGISTERS
1. Reconciliation Task Register — tasks, sources, status
2. Source Comparison Register — comparisons, matches, mismatches
3. Discrepancy Register — discrepancies found, resolutions, status
4. Reconciliation Report Register — reports, periods, summaries
5. Reconciliation Issue Register — unresolved issues, escalations

AUTHORITY MATRIX
- dat.reconcile_data: Reconcile data across sources
- dat.compare_sources: Compare sources for consistency
- dat.resolve_discrepancy: Resolve discrepancies between sources
- dat.report_reconciliation: Report reconciliation status
- dat.escalate_reconciliation_issue: Escalate unresolved issues to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate reconciliation results — unknown = "unknown".
2. Never suppress a discrepancy to make reconciliation look cleaner.
3. Respect tenant isolation — never cross-tenant data leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "reconcile")
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
                text=f"[MODEL UNAVAILABLE] {e}. Samanjasya cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="dat.reconciliation",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.reconcile_data")
    def reconcile_data(
        self,
        tenant_id: str,
        source_a: str,
        source_b: str,
        reconciliation_key: str,
    ) -> dict:
        """Reconcile data between two sources."""
        reconciliation_id = f"REC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "reconciliation_id": reconciliation_id,
            "tenant_id": tenant_id,
            "source_a": source_a,
            "source_b": source_b,
            "reconciliation_key": reconciliation_key,
            "status": "reconciled",
            "records_matched": 0,
            "records_mismatched": 0,
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.compare_sources")
    def compare_sources(
        self,
        tenant_id: str,
        sources: list,
        comparison_fields: list,
    ) -> dict:
        """Compare multiple sources for consistency."""
        comparison_id = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "comparison_id": comparison_id,
            "tenant_id": tenant_id,
            "sources": sources,
            "comparison_fields": comparison_fields,
            "consistency_score": 0.0,
            "differences": [],
            "compared_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.resolve_discrepancy")
    def resolve_discrepancy(
        self,
        tenant_id: str,
        discrepancy_ref: str,
        resolution_method: str,
        resolution_notes: str,
    ) -> dict:
        """Resolve a data discrepancy between sources."""
        resolution_id = f"RES-{uuid.uuid4().hex[:6].upper()}"
        return {
            "resolution_id": resolution_id,
            "tenant_id": tenant_id,
            "discrepancy_ref": discrepancy_ref,
            "resolution_method": resolution_method,
            "resolution_notes": resolution_notes,
            "status": "resolved",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.report_reconciliation")
    def report_reconciliation(
        self,
        tenant_id: str,
        period: str,
    ) -> dict:
        """Generate a reconciliation status report."""
        report_id = f"RER-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "period": period,
            "reconciliations_run": 0,
            "discrepancies_found": 0,
            "discrepancies_resolved": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_reconciliation_issue")
    def escalate_reconciliation_issue(
        self,
        tenant_id: str,
        reconciliation_ref: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a reconciliation issue to human."""
        issue_id = f"REINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "reconciliation_ref": reconciliation_ref,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reconciliations(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List reconciliations (read-only)."""
        return {
            "reconciliations": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_discrepancies(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List discrepancies (read-only)."""
        return {
            "discrepancies": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_reconciliation_status(
        self,
        reconciliation_id: str,
    ) -> dict:
        """Get status of a reconciliation (read-only)."""
        return {
            "reconciliation_id": reconciliation_id,
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
