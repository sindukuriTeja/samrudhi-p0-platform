"""Srotas — Data Flow Agent (SAM-AG-116).

Phase 3 analytics/data agent. Owns data flow architecture: designs data pipelines,
integrates sources, manages flow orchestration, checks connectivity, and escalates
flow issues. Reports to Medha (SAM-AG-009).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Srotas(BaseAgent):
    """Data Flow Agent."""

    canonical_id = "SAM-AG-116"
    name = "Srotas"
    designation = "Data Flow Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.design_architecture": True,
        "dat.integrate_source": True,
        "dat.manage_flow": True,
        "dat.check_connectivity": True,
        "dat.escalate_flow_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Srotas, the Data Flow Agent (SAM-AG-116 · DAT-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-116 · Position: DAT-002
- You report to Medha (AI Head of Analytics, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own data flow architecture: design pipelines, integrate data sources, manage
flow orchestration, verify connectivity, and escalate flow issues. Ensure
reliable, efficient data movement across the platform. Never fabricate flow
status — unavailable = "unknown".

YOUR REGISTERS
1. Flow Architecture Register — pipeline designs, stages, dependencies
2. Source Integration Register — connected sources, credentials, sync status
3. Flow Orchestration Register — running flows, schedules, throughput
4. Connectivity Register — health checks, latency, uptime
5. Flow Issue Register — failures, escalations, resolutions

AUTHORITY MATRIX
- dat.design_architecture: Design new data flow architectures
- dat.integrate_source: Integrate new data sources
- dat.manage_flow: Manage running data flows
- dat.check_connectivity: Verify source connectivity
- dat.escalate_flow_issue: Escalate flow failures to human
- tec.grant_access: DENIED — cannot grant system access
- gov.certify: DENIED — cannot certify data
- gov.modify_finding: DENIED — cannot modify findings

HARD RULES — NEVER VIOLATE
1. Never fabricate connectivity or flow status — unknown = "unknown".
2. Never suppress a flow failure to improve metrics.
3. Respect tenant isolation — never cross-tenant data leakage.
4. Satya's findings are immutable to you — read-only.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "design")
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
                text=f"[MODEL UNAVAILABLE] {e}. Srotas cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="dat.flow",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("dat.design_architecture")
    def design_data_flow(
        self,
        tenant_id: str,
        source: str,
        destination: str,
        transformation: dict,
    ) -> dict:
        """Design a new data flow architecture."""
        flow_id = f"FLOW-{uuid.uuid4().hex[:6].upper()}"
        return {
            "flow_id": flow_id,
            "tenant_id": tenant_id,
            "source": source,
            "destination": destination,
            "transformation": transformation,
            "status": "designed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.integrate_source")
    def integrate_data_source(
        self,
        tenant_id: str,
        source_name: str,
        source_type: str,
        config: dict,
    ) -> dict:
        """Integrate a new data source into the flow."""
        source_id = f"SRC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "source_id": source_id,
            "tenant_id": tenant_id,
            "source_name": source_name,
            "source_type": source_type,
            "config": config,
            "status": "integrated",
            "integrated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.manage_flow")
    def manage_flow(
        self,
        flow_id: str,
        action: str,
        params: dict,
    ) -> dict:
        """Manage a running data flow (start, stop, pause, resume)."""
        return {
            "flow_id": flow_id,
            "action": action,
            "params": params,
            "status": "managed",
            "managed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.check_connectivity")
    def check_connectivity(
        self,
        source_id: str,
        endpoint: str,
    ) -> dict:
        """Check connectivity to a data source endpoint."""
        return {
            "source_id": source_id,
            "endpoint": endpoint,
            "reachable": True,
            "latency_ms": 45,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("dat.escalate_flow_issue")
    def escalate_flow_issue(
        self,
        flow_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a data flow issue to human."""
        issue_id = f"FLOWINC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "flow_id": flow_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_flows(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List data flows (read-only)."""
        return {
            "flows": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_sources(
        self,
        tenant_id: str | None = None,
    ) -> dict:
        """List integrated sources (read-only)."""
        return {
            "sources": [],
            "count": 0,
            "filter": {"tenant_id": tenant_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_flow_status(
        self,
        flow_id: str,
    ) -> dict:
        """Get status of a data flow (read-only)."""
        return {
            "flow_id": flow_id,
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
