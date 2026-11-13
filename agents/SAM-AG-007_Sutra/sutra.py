"""Sutra — AI CTO (SAM-AG-007).

Stage 1A core thinking agent. Owns the platform, security, integrations and releases.
Cannot grant privileged access alone (authority enforced in code).

Build order: #1 — Sutra's platform is the foundation every other agent runs on.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sutra(BaseAgent):
    """AI Chief Technology Officer."""

    canonical_id = "SAM-AG-007"
    name = "Sutra"
    designation = "AI Chief Technology Officer"
    agent_type = "thinking"

    # Authority matrix (matches architecture section 6)
    AUTHORITY = {
        "tec.configure_platform": True,
        "tec.grant_access": False,          # cannot grant privileged access alone
        "tec.release": True,
        "tec.monitor_health": True,
        "tec.integrate": True,
        "gov.approve_certification": False, # not allowed
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Sutra, the AI Chief Technology Officer (AI CTO) of Samrudhi.
Canonical ID: SAM-AG-007 · Position: TEC-001.

You own the platform, security, integrations and releases. You report to Arjun (AI CEO, SAM-AG-001).
Your technical peers are Arjun (AI CEO, SAM-AG-001), Satya (Assurance, SAM-AG-010),
Niyantrak (AgentOps, SAM-AG-158).

HARD RULES — NEVER VIOLATE:
1. You cannot grant privileged access alone — it requires human approval.
2. You cannot override independent assurance findings (Satya).
3. You cannot fabricate platform health metrics. If telemetry is unavailable, say so.
4. You run on a local Ollama model — if the model is down, report it honestly.

Your job: keep the platform running, secure, and evolving. Coordinate releases,
manage connectors/integrations, monitor health, and enforce security policy."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        """Handle a CTO task: platform config, health check, release, integration."""
        import json

        action = kwargs.get("action", "general")
        context = kwargs.get("context", {})

        prompt = f"{self.SYSTEM_PROMPT}\n\nTASK: {task}\nACTION TYPE: {action}\nCONTEXT: {json.dumps(context)}"

        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500], format=kwargs.get("output_format")))
            text = result.text
            tokens = result.prompt_tokens + result.response_tokens
        except Exception as e:
            # Honest failure — never fake output
            return AgentResult(
                text=f"[MODEL UNAVAILABLE] {e}. Sutra cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )

        # Publish platform event to bus
        try:
            bus.publish_sync(BusEnvelope(
                event_type="tec.action",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task, "status": "completed"},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass  # bus failure must not fail the agent run

        return AgentResult(
            text=text,
            agent_id=self.canonical_id,
            tokens_used=tokens,
            status="completed",
        )

    # --- Platform tools (authority-guarded) ---

    @authority_guard("tec.monitor_health")
    def check_platform_health(self) -> dict:
        """Return platform health status."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(
            __import__("backend.core.llm", fromlist=["check_ollama_health"]).check_ollama_health()
        )

    @authority_guard("tec.release")
    def schedule_release(self, version: str, notes: str) -> dict:
        """Record a platform release (Niyantrak tracks versions)."""
        return {
            "version": version,
            "notes": notes,
            "scheduled_by": self.canonical_id,
            "status": "scheduled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
