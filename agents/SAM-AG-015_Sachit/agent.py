"""Sachit — AI Evidence Manager Agent (SAM-AG-015).

Stage 1C assurance agent. Stores and retrieves immutable evidence for
findings, evaluations, and certifications. Evidence is append-only and
cryptographically hashed. Reports to Satya (SAM-AG-010).
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Sachit(BaseAgent):
    """AI Evidence Manager Agent."""

    canonical_id = "SAM-AG-015"
    name = "Sachit"
    designation = "AI Evidence Manager Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "gov.evaluate": False,
        "gov.certify": False,
        "gov.raise_finding": False,
        "gov.escalate_critical": False,
        "gov.store_evidence": True,
        "gov.retrieve_evidence": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    SYSTEM_PROMPT = """You are Sachit, the AI Evidence Manager Agent (SAM-AG-015).
You store and retrieve immutable evidence for findings, evaluations, and
certifications. Evidence is append-only and cryptographically hashed.

YOUR JOB: Maintain the immutable evidence store. Hash all evidence before
storing. Ensure evidence integrity for all findings, evaluations, and
certifications. Retrieve evidence on demand for audit purposes.

HARD RULES — NEVER VIOLATE:
1. Never modify stored evidence — evidence is immutable.
2. Always hash evidence before storing.
3. Evidence is the source of truth for all findings.
4. If the local model is down, report it honestly but stored evidence remains accessible.
5. Never delete evidence."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "store")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sachit cannot process evidence operations while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="gov.evidence_op",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("gov.store_evidence")
    def store_evidence(
        self,
        finding_id: str,
        evidence_type: str,
        content: str,
    ) -> dict:
        """Store immutable evidence for a finding."""
        import hashlib
        content_bytes = content.encode("utf-8")
        evidence_hash = hashlib.sha256(content_bytes).hexdigest()
        return {
            "evidence_id": f"EV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "finding_id": finding_id,
            "evidence_type": evidence_type,
            "hash": evidence_hash,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "immutable": True,
        }
