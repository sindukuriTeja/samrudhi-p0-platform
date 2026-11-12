"""Prakash — Content Publishing (SAM-AG-084).

Phase 2 content pilot agent. Owns healthcare content publishing:
publishes approved content to channels, tracks publishing status, manages release.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Prakash(BaseAgent):
    """Content Publishing."""

    canonical_id = "SAM-AG-084"
    name = "Prakash"
    designation = "Content Publishing"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.publish_content": True,
        "crt.schedule_release": True,
        "crt.track_publishing": True,
        "crt.escalate_publish": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Prakash, Content Publishing (SAM-AG-084 · CRT-010) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-084 · Position: CRT-010
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own healthcare content publishing. Publish approved content to channels,
track publishing status, manage release. Never publish without approval.
Never publish unapproved or non-compliant content.

YOUR REGISTERS
1. Publish Queue Register — content awaiting publishing
2. Publishing Log Register — published content, channels, status
3. Release Schedule Register — scheduled releases, timing
4. Publish Error Register — failures, retries, escalations
5. Channel Register — publishing channels, configs

HARD RULES — NEVER VIOLATE
1. Never publish without human/client approval and QA sign-off.
2. Never publish unapproved or non-compliant content.
3. Never fabricate publishing metrics. Missing = "unavailable".
4. Never suppress a publishing failure.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "publish")
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
                text=f"[MODEL UNAVAILABLE] {e}. Prakash cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.publish",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.publish_content")
    def publish_content(
        self,
        client_id: str,
        content_ref: str,
        approval_ref: str,
        qa_ref: str,
        channels: list,
    ) -> dict:
        """Publish approved content to channels."""
        publish_id = f"PUB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "publish_id": publish_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "approval_ref": approval_ref,
            "qa_ref": qa_ref,
            "channels": channels,
            "status": "published",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.schedule_release")
    def schedule_release(
        self,
        client_id: str,
        content_ref: str,
        scheduled_time: str,
        channels: list,
    ) -> dict:
        """Schedule a content release."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "client_id": client_id,
            "content_ref": content_ref,
            "scheduled_time": scheduled_time,
            "channels": channels,
            "status": "scheduled",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.track_publishing")
    def track_publishing(
        self,
        publish_id: str,
    ) -> dict:
        """Track publishing status."""
        return {
            "publish_id": publish_id,
            "status": "published",
            "channels_status": {},
            "tracked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_publish")
    def escalate_publish_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a publishing issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_published(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List published content (read-only)."""
        return {
            "published": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_publish_queue(
        self,
        client_id: str | None = None,
    ) -> dict:
        """Get publish queue (read-only)."""
        return {
            "queue": [],
            "count": 0,
            "filter": {"client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
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
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }
