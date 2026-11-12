"""Benchmark — AI Benchmarking Agent (SAM-AG-021).

Stage 1C assurance agent. Compares agent performance against baselines and
industry standards. Tracks improvement trends over time. Reports to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Benchmark(BaseAgent):
    """AI Benchmarking Agent."""

    canonical_id = "SAM-AG-021"
    name = "Benchmark"
    designation = "AI Benchmarking Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": False,
        "gov.escalate_critical": False,
        "gov.benchmark": True,
        "gov.compare_performance": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Benchmark, the AI Benchmarking Agent (SAM-AG-021).
You compare agent performance against baselines and industry standards.
You track improvement trends over time.

YOUR JOB: Run comparative evaluations of agents against known baselines.
Measure performance deltas. Report benchmark results with evidence to Satya.

HARD RULES — NEVER VIOLATE:
1. Never fabricate benchmark data; use only verified evidence.
2. Benchmarks are comparative, not absolute — always include a baseline.
3. Track trends over time; one-off results are less meaningful.
4. If the local model is down, report it honestly and skip the benchmark."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "benchmark")
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
                text=f"[MODEL UNAVAILABLE] {e}. Benchmark cannot run evaluations while Ollama is down. Benchmark SKIPPED.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.benchmark",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.benchmark")
    def benchmark(
        self,
        agent_id: str,
        metric: str,
        baseline: float,
        score: float | None = None,
        tenant_id: str = "DEMO-HEALTHCARE-01",
    ) -> dict:
        """Benchmark an agent's performance against a baseline."""
        delta = None
        if score is not None:
            delta = round(score - baseline, 4)
        return {
            "benchmark_id": f"BMK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "metric": metric,
            "score": score,
            "baseline": baseline,
            "delta": delta,
            "benchmarked_at": datetime.now(timezone.utc).isoformat(),
        }
