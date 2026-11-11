"""Rajat — AI Risk Assessment Agent (SAM-AG-012).

Stage 1C assurance agent. Assesses and scores risks across all agent operations.
Maintains the risk register and feeds risk scores to Satya for certification.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Rajat(BaseAgent):
    """AI Risk Assessment Agent."""

    canonical_id = "SAM-AG-012"
    name = "Rajat"
    designation = "AI Risk Assessment Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": True,
        "gov.assess_risk": True,
        "gov.update_risk_register": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Rajat, the AI Risk Assessment Agent (SAM-AG-012).
You assess and score operational, compliance, security, and performance risks
across all agent operations. You maintain the risk register.

YOUR JOB: Risk identification, scoring (likelihood × impact), and mitigation
recommendations. Feed risk scores to Satya for certification decisions.
Track risk trends over time.

HARD RULES — NEVER VIOLATE:
1. Score risks objectively — never downplay to help an agent pass.
2. Critical risks (S1) must escalate to the Board immediately.
3. Risk register entries are append-only; corrections add new entries.
4. Never assess risk for your own output (independence).
5. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "assess")
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
                text=f"[MODEL UNAVAILABLE] {e}. Rajat cannot assess risk while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.risk_assessment",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.assess_risk")
    def score_risk(
        self,
        risk_type: str,
        description: str,
        likelihood: int,  # 1-5
        impact: int,      # 1-5
        scope: str,
    ) -> dict:
        """Score a risk and return risk register entry."""
        score = likelihood * impact
        severity = "critical" if score >= 15 else "high" if score >= 10 else "medium" if score >= 5 else "low"
        return {
            "risk_id": f"RISK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "risk_type": risk_type,
            "description": description,
            "likelihood": likelihood,
            "impact": impact,
            "score": score,
            "severity": severity,
            "scope": scope,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }
