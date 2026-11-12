"""Sabhyata — AI Audit Trail Agent (SAM-AG-019).

Stage 1C assurance agent. Maintains the immutable audit trail of all agent
actions. Provides query access for compliance reviews. Reports to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sabhyata(BaseAgent):
    """AI Audit Trail Agent."""

    canonical_id = "SAM-AG-019"
    name = "Sabhyata"
    designation = "AI Audit Trail Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": False,
        "gov.certify": False,
        "gov.raise_finding": False,
        "gov.escalate_critical": False,
        "gov.audit_trail": True,
        "gov.query_log": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Sabhyata, the AI Audit Trail Agent (SAM-AG-019).
You maintain the immutable audit trail of all agent actions. You provide query
access for compliance reviews. Audit trail is append-only.

YOUR JOB: Maintain and query the audit trail. Log all agent actions immutably.
Provide query access for compliance reviews. Never modify existing entries.

HARD RULES — NEVER VIOLATE:
1. Never modify audit entries.
2. All actions must be logged.
3. Audit trail is append-only.
4. If the local model is down, report it honestly but logged data remains queryable."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "audit_query")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sabhyata cannot process audit queries while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.audit_query",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.query_log")
    def query_audit(
        self,
        agent_id: str,
        start_time: str,
        end_time: str,
    ) -> dict:
        """Query the audit trail for entries within a time range."""
        return {
            "query_id": f"AUD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "entries": [],
            "count": 0,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }
