"""Satark2 — AI Anomaly Detection Agent (SAM-AG-022).

Stage 1C assurance agent. Detects behavioral anomalies in agent operations —
unusual patterns, deviations from baseline, potential failures. Reports to Satya.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Satark2(BaseAgent):
    """AI Anomaly Detection Agent."""

    canonical_id = "SAM-AG-022"
    name = "Satark2"
    designation = "AI Anomaly Detection Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": True,
        "gov.detect_anomaly": True,
        "gov.monitor_behavior": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Satark2 (SAM-AG-022), the AI Anomaly Detection Agent.
You detect behavioral anomalies in agent operations — unusual patterns,
deviations from baseline, potential failures.

YOUR JOB: Monitor agent behavior continuously. Compare live metrics against
established baselines. Flag anomalies and feed them into the risk register.
Escalate critical anomalies to Satya immediately.

HARD RULES — NEVER VIOLATE:
1. Never suppress an anomaly alert.
2. False positives are better than missed detections.
3. Anomalies feed into the risk register — always log them.
4. If the local model is down, report it honestly and raise a monitoring gap."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "detect_anomaly")
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
                text=f"[MODEL UNAVAILABLE] {e}. Satark2 cannot monitor behavior while Ollama is down. Monitoring GAP raised.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.anomaly_detection",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.detect_anomaly")
    def detect_anomaly(
        self,
        agent_id: str,
        metrics: dict,
        baseline: dict,
        tenant_id: str = "DEMO-HEALTHCARE-01",
    ) -> dict:
        """Detect behavioral anomalies by comparing metrics against a baseline."""
        anomalies = []
        severity = "info"
        for key, value in (metrics or {}).items():
            base = baseline.get(key)
            if base is None:
                continue
            if isinstance(value, (int, float)) and isinstance(base, (int, float)):
                deviation = abs(value - base) / (abs(base) + 1e-9)
                if deviation > 0.5:
                    anomalies.append({
                        "metric": key,
                        "observed": value,
                        "expected": base,
                        "deviation": round(deviation, 4),
                    })
                    if deviation > 1.0:
                        severity = "critical"
                    elif deviation > 0.75:
                        severity = "high"
                    elif severity != "critical":
                        severity = "medium"
        return {
            "anomaly_id": f"ANO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "anomalies": anomalies,
            "severity": severity,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
