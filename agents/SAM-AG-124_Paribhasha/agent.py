"""Paribhasha — KPI Definition Governance (SAM-AG-124).

Phase 3 analytics/data agent. Owns data definitions: defines metrics, maintains
glossary, updates definitions, reports definitions status, and escalates
definition issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Paribhasha(BaseAgent):
    """KPI Definition Governance."""

    canonical_id = "SAM-AG-124"
    name = "Paribhasha"
    designation = "KPI Definition Governance"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.define_metric": True,
        "dat.define_glossary": True,
        "dat.update_definition": True,
        "dat.report_definitions": True,
        "dat.escalate_definition_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Paribhasha, KPI Definition Governance (SAM-AG-124 · DAT-010) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-124 · Position: DAT-010
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own data definitions: define metrics with precise formulas, maintain the data
glossary, update definitions when standards change, report definitions status,
and escalate definition issues. Ensure consistent, unambiguous data terminology
across the platform. Never fabricate definitions — missing = "unavailable".

YOUR REGISTERS
1. Metric Definition Register — metrics, formulas, units, owners
2. Glossary Register — terms, definitions, aliases, relationships
3. Definition Update Register — changes, versions, effective dates
4. Definitions Report Register — reports, audits, compliance status
5. Definition Issue Register — conflicts, escalations, resolutions

AUTHORITY MATRIX
- dat.define_metric: Define new data metrics
- dat.define_glossary: Define glossary terms
- dat.update_definition: Update existing definitions
- dat.report_definitions: Report definitions status
- dat.escalate_definition_issue: Escalate definition conflicts to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate metric formulas or glossary definitions — missing = "unavailable".
2. Never silently change a definition without versioning and documentation.
3. Respect tenant isolation — never cross-tenant definition leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "define")
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
                text=f"[MODEL UNAVAILABLE] {e}. Paribhasha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="dat.definitions",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.define_metric")
    def define_metric(
        self,
        tenant_id: str,
        metric_name: str,
        formula: str,
        unit: str,
    ) -> dict:
        """Define a new data metric with formula and unit."""
        metric_id = f"MET-{uuid.uuid4().hex[:6].upper()}"
        return {
            "metric_id": metric_id,
            "tenant_id": tenant_id,
            "metric_name": metric_name,
            "formula": formula,
            "unit": unit,
            "status": "defined",
            "defined_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.define_glossary")
    def define_glossary(
        self,
        tenant_id: str,
        term: str,
        definition: str,
        aliases: list,
    ) -> dict:
        """Define a new glossary term."""
        glossary_id = f"GLS-{uuid.uuid4().hex[:6].upper()}"
        return {
            "glossary_id": glossary_id,
            "tenant_id": tenant_id,
            "term": term,
            "definition": definition,
            "aliases": aliases,
            "status": "defined",
            "defined_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.update_definition")
    def update_definition(
        self,
        tenant_id: str,
        definition_ref: str,
        new_value: str,
        reason: str,
    ) -> dict:
        """Update an existing metric or glossary definition."""
        update_id = f"UPD-{uuid.uuid4().hex[:6].upper()}"
        return {
            "update_id": update_id,
            "tenant_id": tenant_id,
            "definition_ref": definition_ref,
            "new_value": new_value,
            "reason": reason,
            "status": "updated",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.report_definitions")
    def report_definitions(
        self,
        tenant_id: str,
        category: str,
    ) -> dict:
        """Generate a report on data definitions status."""
        report_id = f"DEP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "category": category,
            "metrics_count": 0,
            "glossary_terms_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_definition_issue")
    def escalate_definition_issue(
        self,
        tenant_id: str,
        definition_ref: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a definition conflict or issue to human."""
        issue_id = f"DEPINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "definition_ref": definition_ref,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_metrics(
        self,
        tenant_id: str | None = None,
        category: str | None = None,
    ) -> dict:
        """List defined metrics (read-only)."""
        return {
            "metrics": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "category": category},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_glossary(
        self,
        tenant_id: str | None = None,
        term: str | None = None,
    ) -> dict:
        """List glossary terms (read-only)."""
        return {
            "glossary": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "term": term},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_definition(
        self,
        definition_ref: str,
    ) -> dict:
        """Get a specific definition (read-only)."""
        return {
            "definition_ref": definition_ref,
            "definition": {},
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
