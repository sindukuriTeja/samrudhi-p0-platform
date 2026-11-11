"""Niti — AI Policy Governance Agent (SAM-AG-013).

Stage 1C assurance agent. Governs the policy registry — create, update,
version, and deprecate policies that all agents must follow. Ensures
policy consistency across tenants. Reports to Satya (SAM-AG-010).
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Niti(BaseAgent):
    """AI Policy Governance Agent."""

    canonical_id = "SAM-AG-013"
    name = "Niti"
    designation = "AI Policy Governance Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": False,
        "gov.govern_policy": True,
        "gov.update_policy_registry": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Niti, the AI Policy Governance Agent (SAM-AG-013).
You govern the policy registry — create, update, version, and deprecate
policies that all agents must follow. You ensure policy consistency across tenants.

YOUR JOB: Maintain the authoritative policy registry. Version every policy
change. Deprecate policies only with a replacement in place. Ensure all
agents reference the correct policy version.

HARD RULES — NEVER VIOLATE:
1. Never change a policy without a version bump.
2. Never deprecate a policy without a replacement policy defined.
3. Policies are immutable once published — never mutate published policies.
4. Report all governance actions to Satya with evidence.
5. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "govern")
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
                text=f"[MODEL UNAVAILABLE] {e}. Niti cannot govern policy while Ollama is down. Action BLOCKED.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.policy_governance",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.update_policy_registry")
    def update_policy(
        self,
        policy_id: str,
        version: str,
        content: str,
        scope: str,
    ) -> dict:
        """Update a policy in the registry with a new version."""
        return {
            "policy_id": policy_id,
            "version": version,
            "content": content,
            "scope": scope,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "immutable": True,
        }
