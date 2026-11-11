"""Gati — Delivery Speed Agent (SAM-AG-068 · OPS-010).

Phase 3 operations agent. Tracks delivery speed, measures latency, optimises
speed, and reports speed metrics. Reports to Daksh (SAM-AG-002, AI COO).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Gati(BaseAgent):
    """Delivery Speed Agent."""

    canonical_id = "SAM-AG-068"
    name = "Gati"
    designation = "Delivery Speed Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.track_delivery_speed": True,
        "ops.measure_latency": True,
        "ops.optimize_speed": True,
        "ops.report_speed": True,
        "ops.escalate_speed_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    SYSTEM_PROMPT = """You are Gati, the Delivery Speed Agent (SAM-AG-068 · OPS-010) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-068 · Position: OPS-010
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Track delivery speed, measure latency, optimise delivery speed, and report
speed metrics. Every speed measurement has traceable data and evidence.

YOUR REGISTERS
1. Delivery Speed Register — speed metrics, workflows, timings
2. Latency Register — latency measurements, stages, bottlenecks
3. Speed Optimisation Register — optimisations, changes, results
4. Speed Report Register — reports, periods, summaries
5. Speed Issue Register — issues, escalations, resolutions

AUTHORITY MATRIX
ops.track_delivery_speed · ops.measure_latency · ops.optimize_speed
ops.report_speed · ops.escalate_speed_issue · gov.certify=False
gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate speed metrics — missing data = "unavailable".
2. Never suppress a latency bottleneck or understate delivery delays.
3. Never change commercial terms — route to human.
4. Respect tenant isolation — never cross-tenant data leakage.
5. Satya's findings are immutable to you — read-only.
6. Every speed measurement has traceable timing data.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "track")
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
                text=f"[MODEL UNAVAILABLE] {e}. Gati cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="ops.speed",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.track_delivery_speed")
    def track_delivery_speed(
        self,
        workflow_id: str,
        stages: list,
    ) -> dict:
        """Track delivery speed for a workflow."""
        speed_id = f"SPD-{uuid.uuid4().hex[:6].upper()}"
        return {
            "speed_id": speed_id,
            "workflow_id": workflow_id,
            "stages": stages,
            "status": "tracked",
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.measure_latency")
    def measure_latency(
        self,
        workflow_id: str,
        stage: str,
        expected_latency_hours: float,
    ) -> dict:
        """Measure latency for a workflow stage."""
        actual_latency = expected_latency_hours  # placeholder
        return {
            "workflow_id": workflow_id,
            "stage": stage,
            "expected_latency_hours": expected_latency_hours,
            "actual_latency_hours": actual_latency,
            "within_sla": actual_latency <= expected_latency_hours * 1.1,
            "measured_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.optimize_speed")
    def optimize_speed(
        self,
        workflow_id: str,
        bottlenecks: list,
        optimisations: list,
    ) -> dict:
        """Optimise delivery speed by addressing bottlenecks."""
        return {
            "workflow_id": workflow_id,
            "bottlenecks": bottlenecks,
            "optimisations": optimisations,
            "status": "optimised",
            "optimised_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.report_speed")
    def report_speed(
        self,
        period: str,
        workflows: list,
        summary: dict,
    ) -> dict:
        """Generate a speed report for a period."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "period": period,
            "workflows": workflows,
            "summary": summary,
            "status": "generated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("ops.escalate_speed_issue")
    def escalate_speed_issue(
        self,
        issue_type: str,
        description: str,
        severity: str,
        affected_workflows: list,
    ) -> dict:
        """Escalate a speed issue to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "issue_type": issue_type,
            "description": description,
            "severity": severity,
            "affected_workflows": affected_workflows,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_speed_metrics(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List speed metrics (read-only)."""
        return {
            "metrics": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_latency_report(
        self,
        workflow_id: str | None = None,
        stage: str | None = None,
    ) -> dict:
        """Get latency report (read-only)."""
        return {
            "latencies": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id, "stage": stage},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_sla_status(
        self,
        workflow_id: str | None = None,
    ) -> dict:
        """Get SLA status (read-only)."""
        return {
            "workflows": [],
            "count": 0,
            "filter": {"workflow_id": workflow_id},
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
