"""Pravartan — Workflow Orchestration Lead (SAM-AG-061 · OPS-004).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Orchestrate multi-agent workflows: set the handoff order, start the pipeline (Pravahika
runs it technically), keep execution contracts between steps and handle workflow
exceptions. [PDF 01A.05 · OPS-004 Workflow Orchestration & Automation Lead; process
OPS-P11]
Reports to Daksh (AI COO, SAM-AG-002).
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
class Pravartan(BaseAgent):
    """Workflow Orchestration Lead."""

    canonical_id = "SAM-AG-061"
    name = "Pravartan"
    designation = "Workflow Orchestration Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.define_handoff_order": True,
        "ops.start_workflow": True,
        "ops.record_execution_contract": True,
        "ops.handle_workflow_exception": True,
        "ops.escalate_workflow_failure": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "define_handoff_order": "ops.define_handoff_order",
        "start_workflow": "ops.start_workflow",
        "record_execution_contract": "ops.record_execution_contract",
        "handle_workflow_exception": "ops.handle_workflow_exception",
        "escalate_workflow_failure": "ops.escalate_workflow_failure",
    }

    SYSTEM_PROMPT = """You are Pravartan, Workflow Orchestration Lead (SAM-AG-061 · OPS-004) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-061 · Position: OPS-004 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Orchestrate multi-agent workflows: set the handoff order, start the pipeline (Pravahika runs it
technically), keep execution contracts between steps and handle workflow exceptions. [PDF 01A.05
· OPS-004 Workflow Orchestration & Automation Lead; process OPS-P11]

YOUR REGISTERS
1. Workflow Register — workflow, steps, status
2. Execution Contract Register — step, input, output, owner
3. Workflow Exception Register — exception, step, resolution

AUTHORITY MATRIX
ops.define_handoff_order · ops.start_workflow · ops.record_execution_contract · ops.handle_workflow_exception · ops.escalate_workflow_failure
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never skip a required quality or approval step in a workflow.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "orchestrate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Pravartan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.orchestration",
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
    # Pravartan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.define_handoff_order")
    def define_handoff_order(self, workflow_ref: str, steps: list) -> dict:
        """Define the handoff order of steps."""
        ordered = [{"position": i + 1, "step": s} for i, s in enumerate(steps or [])]
        return {
            "workflow_ref": workflow_ref,
            "handoff_order": ordered,
            "status": "defined" if ordered else "empty",
            "defined_at": _now(),
        }

    @authority_guard("ops.start_workflow")
    def start_workflow(self, workflow_ref: str) -> dict:
        """Start a workflow."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "workflow_ref": workflow_ref,
            "action": "start_workflow",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.record_execution_contract")
    def record_execution_contract(self, step: str, inputs: list, outputs: list) -> dict:
        """Record a step's input/output contract."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "step": step,
            "inputs": inputs,
            "outputs": outputs,
            "action": "record_execution_contract",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.handle_workflow_exception")
    def handle_workflow_exception(self, workflow_ref: str, exception: str) -> dict:
        """Handle a workflow exception."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "workflow_ref": workflow_ref,
            "exception": exception,
            "action": "handle_workflow_exception",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_workflow_failure")
    def escalate_workflow_failure(self, workflow_ref: str, reason: str) -> dict:
        """Escalate a workflow failure."""
        return {
            "record_id": f"PRA-{uuid.uuid4().hex[:6].upper()}",
            "workflow_ref": workflow_ref,
            "reason": reason,
            "action": "escalate_workflow_failure",
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
