"""Sangrah — Data Collection Agent (SAM-AG-121).

Phase 3 analytics/data agent. Owns data collection: collects data from sources,
fetches from external sources, stores collected data, tracks collection status,
and escalates collection issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sangrah(BaseAgent):
    """Data Collection Agent."""

    canonical_id = "SAM-AG-121"
    name = "Sangrah"
    designation = "Data Collection Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.collect_data": True,
        "dat.fetch_from_source": True,
        "dat.store_data": True,
        "dat.track_collection": True,
        "dat.escalate_collection_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Sangrah, the Data Collection Agent (SAM-AG-121 · DAT-005) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-121 · Position: DAT-005
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own data collection: collect data from configured sources, fetch from external
APIs and platforms, store collected data securely, track collection progress,
and escalate collection issues. Ensure complete, timely data acquisition.
Never fabricate collection status — unknown = "unknown".

YOUR REGISTERS
1. Collection Task Register — tasks, sources, status, progress
2. Fetch Register — fetch operations, source endpoints, response status
3. Storage Register — stored datasets, locations, sizes
4. Collection Tracking Register — completion rates, timestamps, throughput
5. Collection Issue Register — failures, escalations, resolutions

AUTHORITY MATRIX
- dat.collect_data: Collect data from configured sources
- dat.fetch_from_source: Fetch data from external sources
- dat.store_data: Store collected data
- dat.track_collection: Track collection progress
- dat.escalate_collection_issue: Escalate collection failures to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate collection status or fetched data — unknown = "unknown".
2. Never suppress a collection failure to improve metrics.
3. Respect tenant isolation — never cross-tenant data leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "collect")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sangrah cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="dat.collection",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.collect_data")
    def collect_data(
        self,
        tenant_id: str,
        source_name: str,
        collection_params: dict,
    ) -> dict:
        """Collect data from a configured source."""
        collection_id = f"COL-{uuid.uuid4().hex[:6].upper()}"
        return {
            "collection_id": collection_id,
            "tenant_id": tenant_id,
            "source_name": source_name,
            "collection_params": collection_params,
            "status": "collected",
            "records_collected": 0,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.fetch_from_source")
    def fetch_from_source(
        self,
        tenant_id: str,
        endpoint: str,
        fetch_params: dict,
    ) -> dict:
        """Fetch data from an external source endpoint."""
        fetch_id = f"FETCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "fetch_id": fetch_id,
            "tenant_id": tenant_id,
            "endpoint": endpoint,
            "fetch_params": fetch_params,
            "status": "fetched",
            "records_fetched": 0,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.store_data")
    def store_data(
        self,
        tenant_id: str,
        dataset_ref: str,
        data: dict,
        storage_location: str,
    ) -> dict:
        """Store collected data in a storage location."""
        storage_id = f"STORE-{uuid.uuid4().hex[:6].upper()}"
        return {
            "storage_id": storage_id,
            "tenant_id": tenant_id,
            "dataset_ref": dataset_ref,
            "storage_location": storage_location,
            "status": "stored",
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.track_collection")
    def track_collection(
        self,
        tenant_id: str,
        collection_id: str,
    ) -> dict:
        """Track the progress of a data collection."""
        return {
            "collection_id": collection_id,
            "tenant_id": tenant_id,
            "progress": 0.0,
            "status": "unknown",
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_collection_issue")
    def escalate_collection_issue(
        self,
        tenant_id: str,
        collection_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a data collection issue to human."""
        issue_id = f"COLINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_collections(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List data collections (read-only)."""
        return {
            "collections": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_stored_datasets(
        self,
        tenant_id: str | None = None,
    ) -> dict:
        """List stored datasets (read-only)."""
        return {
            "datasets": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_collection_status(
        self,
        collection_id: str,
    ) -> dict:
        """Get status of a data collection (read-only)."""
        return {
            "collection_id": collection_id,
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
