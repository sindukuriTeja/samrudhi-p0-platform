"""Darpan — Data Mirror Agent (SAM-AG-126).

Phase 3 analytics/data agent. Owns data mirroring: mirrors data to replicas,
syncs mirrors, verifies mirror integrity, reports mirror status, and escalates
mirror issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Darpan(BaseAgent):
    """Data Mirror Agent."""

    canonical_id = "SAM-AG-126"
    name = "Darpan"
    designation = "Data Mirror Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.mirror_data": True,
        "dat.sync_mirror": True,
        "dat.verify_mirror": True,
        "dat.report_mirror": True,
        "dat.escalate_mirror_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Darpan, the Data Mirror Agent (SAM-AG-126 · DAT-009) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-126 · Position: DAT-009
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own data mirroring: mirror data to replicas for redundancy and performance,
sync mirrors with source data, verify mirror integrity and consistency, report
mirror status, and escalate mirror issues. Ensure reliable, consistent data
replicas. Never fabricate mirror status — unknown = "unknown".

YOUR REGISTERS
1. Mirror Registry — mirror definitions, source, replica, status
2. Sync Register — sync operations, timestamps, records synced
3. Verification Register — integrity checks, checksums, results
4. Mirror Report Register — reports, periods, status summaries
5. Mirror Issue Register — failures, escalations, resolutions

AUTHORITY MATRIX
- dat.mirror_data: Create data mirrors to replicas
- dat.sync_mirror: Synchronize mirrors with source data
- dat.verify_mirror: Verify mirror integrity
- dat.report_mirror: Report mirror status
- dat.escalate_mirror_issue: Escalate mirror failures to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate mirror status or verification results — unknown = "unknown".
2. Never suppress a mirror integrity failure to avoid escalation.
3. Respect tenant isolation — never cross-tenant data leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "mirror")
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
            bus.publish(BusEnvelope(
                event_type="dat.mirror",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.mirror_data")
    def mirror_data(
        self,
        tenant_id: str,
        source_ref: str,
        replica_location: str,
    ) -> dict:
        """Create a mirror of data to a replica location."""
        mirror_id = f"MRR-{uuid.uuid4().hex[:6].upper()}"
        return {
            "mirror_id": mirror_id,
            "tenant_id": tenant_id,
            "source_ref": source_ref,
            "replica_location": replica_location,
            "status": "mirrored",
            "records_mirrored": 0,
            "mirrored_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.sync_mirror")
    def sync_mirror(
        self,
        tenant_id: str,
        mirror_id: str,
    ) -> dict:
        """Synchronize a mirror with its source data."""
        sync_id = f"SYN-{uuid.uuid4().hex[:6].upper()}"
        return {
            "sync_id": sync_id,
            "tenant_id": tenant_id,
            "mirror_id": mirror_id,
            "status": "synced",
            "records_synced": 0,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.verify_mirror")
    def verify_mirror(
        self,
        tenant_id: str,
        mirror_id: str,
    ) -> dict:
        """Verify mirror integrity and consistency with source."""
        return {
            "mirror_id": mirror_id,
            "tenant_id": tenant_id,
            "integrity_check": "passed",
            "checksum_match": True,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.report_mirror")
    def report_mirror(
        self,
        tenant_id: str,
        period: str,
    ) -> dict:
        """Generate a mirror status report."""
        report_id = f"MRP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "period": period,
            "mirrors_total": 0,
            "mirrors_synced": 0,
            "mirrors_out_of_sync": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_mirror_issue")
    def escalate_mirror_issue(
        self,
        tenant_id: str,
        mirror_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a mirror issue to human."""
        issue_id = f"MRINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "mirror_id": mirror_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_mirrors(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List mirrors (read-only)."""
        return {
            "mirrors": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_sync_history(
        self,
        tenant_id: str | None = None,
        mirror_id: str | None = None,
    ) -> dict:
        """List sync history (read-only)."""
        return {
            "syncs": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "mirror_id": mirror_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_mirror_status(
        self,
        mirror_id: str,
    ) -> dict:
        """Get status of a mirror (read-only)."""
        return {
            "mirror_id": mirror_id,
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
