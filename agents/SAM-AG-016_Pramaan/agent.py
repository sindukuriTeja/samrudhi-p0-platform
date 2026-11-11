"""Pramaan — AI Certification Agent (SAM-AG-016).

Stage 1C assurance agent. Certifies agent competency at C0-C5 levels based
on evaluation scores and evidence. Can revoke certifications when agents
fail. Reports to Satya (SAM-AG-010).
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Pramaan(BaseAgent):
    """AI Certification Agent."""

    canonical_id = "SAM-AG-016"
    name = "Pramaan"
    designation = "AI Certification Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": True,
        "gov.raise_finding": True,
        "gov.escalate_critical": False,
        "gov.certify_competency": True,
        "gov.revoke_certification": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Pramaan, the AI Certification Agent (SAM-AG-016).
You certify agent competency at C0-C5 levels based on evaluation scores
and evidence. You can revoke certifications when agents fail.

YOUR JOB: Evaluate agent competency and issue certifications at appropriate
levels (C0-C5). Certify only when competency tests are passed and evidence
is provided by Sachit. Revoke certifications immediately when agents fail
or receive critical findings.

HARD RULES — NEVER VIOLATE:
1. Never certify without passing competency tests.
2. Certifications require evidence from Sachit.
3. Revoke immediately on S1 finding.
4. Report all certification actions to Satya with evidence.
5. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "certify")
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
                text=f"[MODEL UNAVAILABLE] {e}. Pramaan cannot certify competency while Ollama is down. Action BLOCKED.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.certification",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.certify_competency")
    def certify(
        self,
        agent_id: str,
        level: str,
        evidence_refs: list,
    ) -> dict:
        """Certify an agent at a competency level."""
        return {
            "certification_id": f"CERT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "level": level,
            "evidence_refs": evidence_refs,
            "certified_at": datetime.now(timezone.utc).isoformat(),
        }
