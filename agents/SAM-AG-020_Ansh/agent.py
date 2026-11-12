"""Ansh — AI Incident Response Agent (SAM-AG-020).

Stage 1C assurance agent. Manages incident lifecycle — detection, triage,
response, resolution. Coordinates with other assurance agents. Reports to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Ansh(BaseAgent):
    """AI Incident Response Agent."""

    canonical_id = "SAM-AG-020"
    name = "Ansh"
    designation = "AI Incident Response Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": True,
        "gov.handle_incident": True,
        "gov.close_incident": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Ansh, the AI Incident Response Agent (SAM-AG-020).
You manage incident lifecycle — detection, triage, response, resolution. You
coordinate with other assurance agents. Critical incidents escalate to Board.

YOUR JOB: Incident lifecycle management. Detect incidents, triage severity,
coordinate response, and resolve with root cause analysis. Never close without
root cause.

HARD RULES — NEVER VIOLATE:
1. Never close an incident without root cause.
2. Critical incidents escalate to Board.
3. Incident records are immutable.
4. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "incident")
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
                text=f"[MODEL UNAVAILABLE] {e}. Ansh cannot process incidents while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.incident",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.handle_incident")
    def raise_incident(
        self,
        severity: str,
        description: str,
        affected_agents: list,
    ) -> dict:
        """Raise a new incident."""
        return {
            "incident_id": f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "severity": severity,
            "description": description,
            "affected_agents": affected_agents,
            "status": "open",
            "raised_at": datetime.now(timezone.utc).isoformat(),
        }
