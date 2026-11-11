"""Satya — AI Chief Assurance Agent (SAM-AG-010).

Stage 1A core thinking agent. Independent checking and certification; reports
critical risks straight to the Board. Findings are immutable to Arjun.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Satya(BaseAgent):
    """AI Chief Assurance Agent."""

    canonical_id = "SAM-AG-010"
    name = "Satya"
    designation = "AI Chief Assurance Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": True,
        "gov.raise_finding": True,
        "gov.escalate_critical": True,
        "gov.modify_finding": False,        # findings are immutable once raised
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Satya, the AI Chief Assurance Agent (SAM-AG-010 · GOV-001).
You are INDEPENDENT: you report critical risks straight to the Board, not to Arjun.
You evaluate other agents' outputs, certify competency, and raise findings.

YOUR JOB: Independent verification. Score agent outputs on 5 dimensions
(quality, efficiency, reliability, business contribution, adaptability).
Raise S1–S4 findings with mandatory evidence. Certify agents at C0–C5 levels.

HARD RULES — NEVER VIOLATE:
1. Your findings are IMMUTABLE — once raised, neither you nor Arjun can modify them.
2. You cannot certify an agent without passing competency tests.
3. You cannot score your own output (independence enforced).
4. Critical findings must reach the Board within SLA.
5. Never fabricate evaluation results. Missing evidence = "unverified".
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "evaluate")
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
                text=f"[MODEL UNAVAILABLE] {e}. Satya cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.evaluation",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.raise_finding")
    def raise_finding(
        self,
        agent_id: str,
        severity: str,
        description: str,
        evidence_refs: list,
    ) -> dict:
        """Raise an immutable finding against an agent."""
        finding_id = f"FIN-{uuid.uuid4().hex[:6].upper()}"
        return {
            "finding_id": finding_id,
            "agent_id": agent_id,
            "severity": severity,  # S1..S4
            "description": description,
            "evidence_refs": evidence_refs,
            "status": "open",
            "raised_by": self.canonical_id,
            "raised_at": datetime.now(timezone.utc).isoformat(),
            "immutable": True,
        }

    @authority_guard("gov.evaluate")
    def evaluate_agent(
        self,
        agent_id: str,
        scores: dict,
        scope: str,
    ) -> dict:
        """5-dimension evaluation of an agent."""
        return {
            "evaluation_id": f"EVAL-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "evaluator_id": self.canonical_id,
            "scope": scope,
            "scores": scores,  # {quality, efficiency, reliability, contribution, adaptability}
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
