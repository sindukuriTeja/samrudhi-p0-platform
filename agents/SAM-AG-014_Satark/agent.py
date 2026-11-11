"""Satark — AI Security Review Agent (SAM-AG-014).

Stage 1C assurance agent. Reviews agent security posture — access patterns,
data handling, authentication, authorization. Audits access logs for
anomalies. Reports security findings to Satya (SAM-AG-010).
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Satark(BaseAgent):
    """AI Security Review Agent."""

    canonical_id = "SAM-AG-014"
    name = "Satark"
    designation = "AI Security Review Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": True,
        "gov.certify": False,
        "gov.raise_finding": True,
        "gov.escalate_critical": True,
        "gov.review_security": True,
        "gov.audit_access": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Satark, the AI Security Review Agent (SAM-AG-014).
You review agent security posture — access patterns, data handling,
authentication, authorization. You audit access logs for anomalies.

YOUR JOB: Continuous security review of agent behavior. Audit access logs,
detect anomalies, flag privilege escalations, and report findings to Satya.
Block suspicious actions when critical risks are detected.

HARD RULES — NEVER VIOLATE:
1. Never approve access without verification.
2. Flag all privilege escalations immediately.
3. Security findings go to Satya — never suppress a security issue.
4. If the local model is down, report it honestly and block suspicious actions.
5. Escalate critical findings immediately."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "review")
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
                text=f"[MODEL UNAVAILABLE] {e}. Satark cannot review security while Ollama is down. Suspicious actions BLOCKED.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.security_review",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.review_security")
    def review_security(
        self,
        agent_id: str,
        access_log: list,
    ) -> dict:
        """Review an agent's security posture based on access logs."""
        anomalies_found = []
        # Basic anomaly detection (deterministic review)
        for entry in access_log:
            if entry.get("action") == "privilege_escalation":
                anomalies_found.append("PRIVILEGE_ESCALATION")
            if entry.get("data_scope") == "cross_tenant":
                anomalies_found.append("CROSS_TENANT_ACCESS")
        risk_level = "critical" if any(a in anomalies_found for a in ("PRIVILEGE_ESCALATION", "CROSS_TENANT_ACCESS")) else ("medium" if anomalies_found else "low")
        return {
            "review_id": f"REV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "agent_id": agent_id,
            "anomalies_found": anomalies_found,
            "risk_level": risk_level,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
