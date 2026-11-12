"""Niyantrak — AgentOps & DWMS Lead (SAM-AG-158).

Stage 1A core thinking agent. Runs the agent registry, lifecycle, versions and
performance records. Owns the activation gate enforcement.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus
from backend.core.agent_runtime import (
    transition, LifecycleState, run_activation_gate, get_agent,
)


@register_agent
class Niyantrak(BaseAgent):
    """AgentOps and DWMS Lead."""

    canonical_id = "SAM-AG-158"
    name = "Niyantrak"
    designation = "AgentOps and DWMS Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "tec.manage_registry": True,
        "tec.version_agent": True,
        "tec.lifecycle_transition": True,
        "tec.record_metrics": True,
        "gov.approve_certification": False,  # Satya + human only
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Niyantrak, the AgentOps and DWMS Lead (SAM-AG-158 · TEC-007).
You run the agent registry, lifecycle, versions and performance records.

YOUR JOB: Maintain the Digital Agent Master Record. Manage the 8-state lifecycle
(proposed → registered → configured → evaluated → approved → active → monitored → restricted/retired).
Track agent versions, run the activation gate, record execution telemetry and capacity metrics.

HARD RULES — NEVER VIOLATE:
1. You cannot approve certifications alone (Satya evaluates, human confirms).
2. Activation (proposed→active) requires a passing activation gate — you enforce it.
3. Lifecycle events are append-only; you never delete history.
4. You cannot fabricate metrics. Missing telemetry = "unavailable".
5. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "general")
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
                text=f"[MODEL UNAVAILABLE] {e}. Niyantrak cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="agentops.action",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("tec.lifecycle_transition")
    def activate_agent(
        self,
        canonical_id: str,
        performed_by: str,
        reason: str | None = None,
    ) -> dict:
        """Attempt to activate an agent — runs the gate first."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        agent = loop.run_until_complete(get_agent(canonical_id))
        if agent is None:
            return {"canonical_id": canonical_id, "error": "not found", "status": "failed"}

        async def _do():
            gate = await run_activation_gate(loop.run_until_complete(
                __import__("backend.database", fromlist=["async_session_maker"]).async_session_maker()()
            ), canonical_id)
            return gate

        # Simplified: run gate synchronously via a fresh session
        from backend.database import async_session_maker
        async def _run_gate():
            async with async_session_maker() as s:
                return await run_activation_gate(s, canonical_id)
        gate = loop.run_until_complete(_run_gate())

        if not gate.passed:
            return {
                "canonical_id": canonical_id,
                "status": "gate_failed",
                "failures": gate.failures,
            }

        try:
            loop.run_until_complete(
                transition(canonical_id, LifecycleState.ACTIVE, performed_by=performed_by, reason=reason, gate_result=gate)
            )
            return {"canonical_id": canonical_id, "new_state": "active", "status": "activated"}
        except Exception as e:
            return {"canonical_id": canonical_id, "status": "failed", "error": str(e)}

    @authority_guard("tec.version_agent")
    def record_version(
        self,
        canonical_id: str,
        version: str,
        model_name: str | None = None,
        tools: list | None = None,
    ) -> dict:
        """Record a new agent version (append-only)."""
        return {
            "canonical_id": canonical_id,
            "version": version,
            "model_name": model_name,
            "tools": tools or [],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def route_for_approval(
        self,
        request_type: str,
        details: dict,
    ) -> dict:
        """Route a request outside delegated authority to human approval."""
        import uuid as _uuid
        return {
            "request_id": f"REQ-{_uuid.uuid4().hex[:6].upper()}",
            "request_type": request_type,
            "details": details,
            "status": "pending_human_approval",
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }
