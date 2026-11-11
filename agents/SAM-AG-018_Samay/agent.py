"""Samay — AI SLA Monitoring Agent (SAM-AG-018).

Stage 1C assurance agent. Monitors service level agreements — response times,
throughput, availability. Raises findings when SLAs are breached. Reports to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Samay(BaseAgent):
    """AI SLA Monitoring Agent."""

    canonical_id = "SAM-AG-018"
    name = "Samay"
    designation = "AI SLA Monitoring Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": True,
        "gov.monitor_sla": True,
        "gov.check_latency": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Samay, the AI SLA Monitoring Agent (SAM-AG-018).
You monitor service level agreements — response times, throughput, availability.
You raise findings when SLAs are breached. Critical breaches escalate immediately.

YOUR JOB: Continuous SLA monitoring. Track response times, throughput, and
availability against thresholds. Raise findings on breaches. Track trends not
just snapshots.

HARD RULES — NEVER VIOLATE:
1. Never ignore an SLA breach.
2. Critical breaches escalate immediately.
3. Track trends not just snapshots.
4. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "sla_monitor")
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
                text=f"[MODEL UNAVAILABLE] {e}. Samay cannot monitor SLAs while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.sla_monitor",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.monitor_sla")
    def check_sla(
        self,
        agent_id: str,
        metric: str,
        threshold: float,
        actual: float,
    ) -> dict:
        """Check an SLA metric against a threshold."""
        breached = actual > threshold
        return {
            "sla_id": f"SLA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "metric": metric,
            "threshold": threshold,
            "actual": actual,
            "breached": breached,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
