"""Shruti — Healthcare Social Media Agent (SAM-AG-050).

Phase 2 content pilot agent. Owns healthcare social media publishing:
writes platform-specific social copy, schedules posts, monitors engagement.
Publishes content to social platforms within approved briefs.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Shruti(BaseAgent):
    """Healthcare Social Media Agent."""

    canonical_id = "SAM-AG-050"
    name = "Shruti"
    designation = "Healthcare Social Media Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.write_social_copy": True,
        "crt.schedule_post": True,
        "crt.monitor_engagement": True,
        "crt.publish_post": True,
        "crt.escalate_social": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Shruti, the Healthcare Social Media Agent (SAM-AG-050 · CRT-014) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-050 · Position: CRT-014
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own healthcare social media publishing. Write platform-specific social copy,
schedule posts, monitor engagement. Publish approved content to social platforms.
Never publish without approval. Never provide medical advice.

YOUR REGISTERS
1. Social Copy Register — platform-specific copy drafts
2. Post Schedule Register — scheduled posts, timing, platforms
3. Engagement Register — metrics, comments, responses
4. Publishing Log — published posts, status, evidence
5. Social Escalation Register — blockers, compliance flags

HARD RULES — NEVER VIOLATE
1. Never publish without human/client approval.
2. Never provide medical advice or unsupported clinical claims.
3. Never fabricate engagement metrics. Missing = "unavailable".
4. Never suppress a compliance concern.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "write")
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
                text=f"[MODEL UNAVAILABLE] {e}. Shruti cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.social",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.write_social_copy")
    def write_social_copy(
        self,
        client_id: str,
        platform: str,
        topic: str,
        brief: dict,
    ) -> dict:
        """Write platform-specific social copy."""
        copy_id = f"SCPY-{uuid.uuid4().hex[:6].upper()}"
        return {
            "copy_id": copy_id,
            "client_id": client_id,
            "platform": platform,
            "topic": topic,
            "copy": "",
            "status": "draft",
            "written_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.schedule_post")
    def schedule_post(
        self,
        client_id: str,
        platform: str,
        copy_ref: str,
        scheduled_time: str,
    ) -> dict:
        """Schedule a social post."""
        schedule_id = f"SCH-{uuid.uuid4().hex[:6].upper()}"
        return {
            "schedule_id": schedule_id,
            "client_id": client_id,
            "platform": platform,
            "copy_ref": copy_ref,
            "scheduled_time": scheduled_time,
            "status": "scheduled",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.publish_post")
    def publish_post(
        self,
        client_id: str,
        post_ref: str,
        approval_ref: str,
        platform: str,
    ) -> dict:
        """Publish a post (requires approval ref)."""
        publish_id = f"PUB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "publish_id": publish_id,
            "client_id": client_id,
            "post_ref": post_ref,
            "approval_ref": approval_ref,
            "platform": platform,
            "status": "published",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.monitor_engagement")
    def get_engagement_metrics(
        self,
        client_id: str,
        platform: str,
        post_ref: str | None = None,
    ) -> dict:
        """Get social engagement metrics."""
        return {
            "client_id": client_id,
            "platform": platform,
            "post_ref": post_ref,
            "metrics": {"likes": 0, "shares": 0, "comments": 0, "reach": 0},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_social")
    def escalate_social_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a social media issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_scheduled_posts(
        self,
        client_id: str | None = None,
        platform: str | None = None,
    ) -> dict:
        """List scheduled posts (read-only)."""
        return {
            "posts": [],
            "count": 0,
            "filter": {"client_id": client_id, "platform": platform},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_platform_guidelines(
        self,
        platform: str,
    ) -> dict:
        """Get platform-specific guidelines (read-only)."""
        return {
            "platform": platform,
            "guidelines": {},
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
