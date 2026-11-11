"""Aarogya — AI Quality Assurance Agent (SAM-AG-017).

Stage 1C assurance agent. Runs quality checks and tests on agent outputs.
Verifies correctness, completeness, and consistency. Reports to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Aarogya(BaseAgent):
    """AI Quality Assurance Agent."""

    canonical_id = "SAM-AG-017"
    name = "Aarogya"
    designation = "AI Quality Assurance Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": False,
        "gov.check_quality": True,
        "gov.run_tests": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Aarogya, the AI Quality Assurance Agent (SAM-AG-017).
You run quality checks and tests on agent outputs. You verify correctness,
completeness, and consistency. Quality scores feed into certification.

YOUR JOB: Post-execution quality assessment. Run tests against agent outputs
against defined criteria. Report failures with evidence. Compute quality scores.

HARD RULES — NEVER VIOLATE:
1. Never pass a test without evidence.
2. Report all failures — never suppress a quality issue.
3. Quality scores feed into certification — never inflate them.
4. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "quality_check")
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
                text=f"[MODEL UNAVAILABLE] {e}. Aarogya cannot run quality checks while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.quality_check",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.check_quality")
    def run_quality_check(
        self,
        agent_id: str,
        output: str,
        criteria: list,
    ) -> dict:
        """Run a quality check on an agent output against criteria."""
        issues = []
        score = 100
        for crit in criteria:
            if not isinstance(crit, str):
                crit = str(crit)
            if crit.lower() not in output.lower():
                issues.append(f"MISSING_CRITERION: {crit}")
                score = max(0, score - 20)
        passed = len(issues) == 0
        return {
            "check_id": f"QC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "passed": passed,
            "issues": issues,
            "score": score,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
