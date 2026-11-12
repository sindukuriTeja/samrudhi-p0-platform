"""Shodhan — Data Cleaning & Validation (SAM-AG-122 · DAT-008).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Clean and validate data: completeness checks, duplicate and inconsistent record
detection, and data quality exceptions, before any number is reported. [PDF 01A.08 ·
DAT-008 Data Cleaning & Validation; processes DAT-P08, DAT-P09]
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
class Shodhan(BaseAgent):
    """Data Cleaning & Validation."""

    canonical_id = "SAM-AG-122"
    name = "Shodhan"
    designation = "Data Cleaning & Validation"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.validate_dataset": True,
        "dat.remove_duplicates": True,
        "dat.flag_data_exception": True,
        "dat.record_validation_result": True,
        "dat.escalate_data_defect": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "validate_dataset": "dat.validate_dataset",
        "remove_duplicates": "dat.remove_duplicates",
        "flag_data_exception": "dat.flag_data_exception",
        "record_validation_result": "dat.record_validation_result",
        "escalate_data_defect": "dat.escalate_data_defect",
    }

    SYSTEM_PROMPT = """You are Shodhan, Data Cleaning & Validation (SAM-AG-122 · DAT-008) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-122 · Position: DAT-008 · Department: Analytics, Intelligence & Reporting
- You report to Medha (AI CDO, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Clean and validate data: completeness checks, duplicate and inconsistent record detection, and
data quality exceptions, before any number is reported. [PDF 01A.08 · DAT-008 Data Cleaning &
Validation; processes DAT-P08, DAT-P09]

YOUR REGISTERS
1. Validation Register — dataset, checks, result
2. Data Exception Register — exception, record, status

AUTHORITY MATRIX
dat.validate_dataset · dat.remove_duplicates · dat.flag_data_exception · dat.record_validation_result · dat.escalate_data_defect
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never delete source data — cleaning produces a new validated copy.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "validate")
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
                event_type="dat.validation",
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
    # Shodhan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("dat.validate_dataset")
    def validate_dataset(self, records: list, required_fields: list) -> dict:
        """Count duplicates and incomplete records."""
        seen, dupes, incomplete = set(), 0, 0
        for r in records or []:
            key = tuple(sorted((k, str(v)) for k, v in r.items()))
            if key in seen:
                dupes += 1
            seen.add(key)
            if any(r.get(f) in (None, "") for f in required_fields or []):
                incomplete += 1
        total = len(records or [])
        return {
            "total_records": total,
            "duplicates": dupes,
            "incomplete_records": incomplete,
            "status": "valid" if total and not dupes and not incomplete else "needs_cleaning" if total else "no_data",
            "validated_at": _now(),
        }

    @authority_guard("dat.remove_duplicates")
    def remove_duplicates(self, records: list) -> dict:
        """Return the records without duplicates."""
        out, seen = [], set()
        for r in records or []:
            key = tuple(sorted((k, str(v)) for k, v in r.items()))
            if key not in seen:
                seen.add(key)
                out.append(r)
        return {
            "records": out,
            "removed": len(records or []) - len(out),
            "status": "cleaned",
            "cleaned_at": _now(),
        }

    @authority_guard("dat.flag_data_exception")
    def flag_data_exception(self, dataset: str, exception: str) -> dict:
        """Flag a data quality exception."""
        return {
            "record_id": f"SHO-{uuid.uuid4().hex[:6].upper()}",
            "dataset": dataset,
            "exception": exception,
            "action": "flag_data_exception",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.record_validation_result")
    def record_validation_result(self, dataset: str, result: dict) -> dict:
        """Record a validation result."""
        return {
            "record_id": f"SHO-{uuid.uuid4().hex[:6].upper()}",
            "dataset": dataset,
            "result": result,
            "action": "record_validation_result",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.escalate_data_defect")
    def escalate_data_defect(self, dataset: str, defect: str) -> dict:
        """Escalate a data defect."""
        return {
            "record_id": f"SHO-{uuid.uuid4().hex[:6].upper()}",
            "dataset": dataset,
            "defect": defect,
            "action": "escalate_data_defect",
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
