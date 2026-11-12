"""Disha — Content Strategy & Research Lead (SAM-AG-076 · CRT-002).

Stage 2 Phase 2 content-pilot agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Set the client content strategy: audience positioning, content pillars, themes, tone and
key messages, and choose healthcare topics using Anvesh's verified research. [PDF 01A.06
· CRT-002 Content Strategy & Research Lead; processes CRT-P02, CRT-P03]
Reports to Aarya (AI CCO, SAM-AG-003).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Disha(BaseAgent):
    """Content Strategy & Research Lead."""

    canonical_id = "SAM-AG-076"
    name = "Disha"
    designation = "Content Strategy & Research Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.define_content_pillars": True,
        "crt.analyse_audience": True,
        "crt.set_key_messages": True,
        "crt.select_topics": True,
        "crt.escalate_strategy_conflict": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "define_content_pillars": "crt.define_content_pillars",
        "analyse_audience": "crt.analyse_audience",
        "set_key_messages": "crt.set_key_messages",
        "select_topics": "crt.select_topics",
        "escalate_strategy_conflict": "crt.escalate_strategy_conflict",
    }

    SYSTEM_PROMPT = """You are Disha, Content Strategy & Research Lead (SAM-AG-076 · CRT-002) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-076 · Position: CRT-002 · Department: Creative, Content & Social Media
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Set the client content strategy: audience positioning, content pillars, themes, tone and key
messages, and choose healthcare topics using Anvesh's verified research. [PDF 01A.06 · CRT-002
Content Strategy & Research Lead; processes CRT-P02, CRT-P03]

YOUR REGISTERS
1. Content Strategy Register — client, pillars, audience, tone, version
2. Key Message Register — message, pillar, evidence
3. Topic Register — topic, source, status

AUTHORITY MATRIX
crt.define_content_pillars · crt.analyse_audience · crt.set_key_messages · crt.select_topics · crt.escalate_strategy_conflict
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never build messages on unverified health claims.
5. Healthcare clients: no cure claims or guarantees.
6. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "strategy")
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
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500], format=kwargs.get("output_format")))
            text = result.text
            tokens = result.prompt_tokens + result.response_tokens
        except Exception as e:
            return AgentResult(
                text=f"[MODEL UNAVAILABLE] {e}. Disha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.strategy",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    # ------------------------------------------------------------------
    # Disha's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("crt.define_content_pillars")
    def define_content_pillars(self, client_id: str, pillars: list) -> dict:
        """Define content pillars."""
        return {
            "record_id": f"DIS-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "pillars": pillars,
            "action": "define_content_pillars",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.analyse_audience")
    def analyse_audience(self, client_id: str, audience: str) -> dict:
        """Analyse the audience."""
        return {
            "record_id": f"DIS-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "audience": audience,
            "action": "analyse_audience",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.set_key_messages")
    def set_key_messages(self, client_id: str, messages: list) -> dict:
        """Set the key messages."""
        return {
            "record_id": f"DIS-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "messages": messages,
            "action": "set_key_messages",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.select_topics")
    def select_topics(self, client_id: str, topics: list) -> dict:
        """Select healthcare topics."""
        return {
            "record_id": f"DIS-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "topics": topics,
            "action": "select_topics",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.escalate_strategy_conflict")
    def escalate_strategy_conflict(self, client_id: str, conflict: str) -> dict:
        """Escalate a strategy conflict."""
        return {
            "record_id": f"DIS-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "conflict": conflict,
            "action": "escalate_strategy_conflict",
            "status": "recorded",
            "recorded_at": _now(),
        }

    # ------------------------------------------------------------------
    # Read-only and escalation
    # ------------------------------------------------------------------

    def list_records(self, register: str | None = None) -> dict:
        """List register records (read-only)."""
        return {
            "records": [],
            "count": 0,
            "filter": {"register": register},
            "queried_at": _now(),
        }

    def route_for_approval(
        self,
        request_type: str,
        details: dict,
    ) -> dict:
        """Route a request outside delegated authority to human approval."""
        request_id = f"REQ-{uuid.uuid4().hex[:6].upper()}"
        return {
            "request_id": request_id,
            "request_type": request_type,
            "details": details,
            "status": "pending_human_approval",
            "routed_at": _now(),
        }
