"""Tarangini — Social Media & Distribution Lead (SAM-AG-079 · CRT-005).

Stage 2 Phase 2 content-pilot agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Own social media distribution: pick the platform, format and posting time for each
approved post, keep the distribution plan and platform standards, and coordinate with
Prakash for publishing. Tarangini manages client social media; Tarang markets Samrudhi
itself. [PDF 01A.06 · CRT-005 Social Media & Distribution Lead]
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
class Tarangini(BaseAgent):
    """Social Media & Distribution Lead."""

    canonical_id = "SAM-AG-079"
    name = "Tarangini"
    designation = "Social Media & Distribution Lead"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.create_distribution_plan": True,
        "crt.set_platform_format": True,
        "crt.schedule_posting_slot": True,
        "crt.check_platform_rules": True,
        "crt.escalate_distribution_issue": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "create_distribution_plan": "crt.create_distribution_plan",
        "set_platform_format": "crt.set_platform_format",
        "schedule_posting_slot": "crt.schedule_posting_slot",
        "check_platform_rules": "crt.check_platform_rules",
        "escalate_distribution_issue": "crt.escalate_distribution_issue",
    }

    SYSTEM_PROMPT = """You are Tarangini, Social Media & Distribution Lead (SAM-AG-079 · CRT-005) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-079 · Position: CRT-005 · Department: Creative, Content & Social Media
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own social media distribution: pick the platform, format and posting time for each approved
post, keep the distribution plan and platform standards, and coordinate with Prakash for
publishing. Tarangini manages client social media; Tarang markets Samrudhi itself. [PDF 01A.06 ·
CRT-005 Social Media & Distribution Lead]

YOUR REGISTERS
1. Distribution Plan Register — post, platform, format, time
2. Platform Standards Register — platform, rule, version

AUTHORITY MATRIX
crt.create_distribution_plan · crt.set_platform_format · crt.schedule_posting_slot · crt.check_platform_rules · crt.escalate_distribution_issue
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never publish — publishing is Prakash's job and only for approved content.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "distribute")
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
                text=f"[MODEL UNAVAILABLE] {e}. Tarangini cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.distribution",
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
    # Tarangini's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("crt.create_distribution_plan")
    def create_distribution_plan(self, client_id: str, posts: list) -> dict:
        """Create the distribution plan."""
        return {
            "record_id": f"TAR-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "posts": posts,
            "action": "create_distribution_plan",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.set_platform_format")
    def set_platform_format(self, post_id: str, platform: str, content_format: str) -> dict:
        """Set a post's platform and format."""
        return {
            "record_id": f"TAR-{uuid.uuid4().hex[:6].upper()}",
            "post_id": post_id,
            "platform": platform,
            "content_format": content_format,
            "action": "set_platform_format",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.schedule_posting_slot")
    def schedule_posting_slot(self, post_id: str, slot: str) -> dict:
        """Pick a posting time."""
        return {
            "record_id": f"TAR-{uuid.uuid4().hex[:6].upper()}",
            "post_id": post_id,
            "slot": slot,
            "action": "schedule_posting_slot",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.check_platform_rules")
    def check_platform_rules(self, post_id: str, platform: str) -> dict:
        """Check platform rules."""
        return {
            "record_id": f"TAR-{uuid.uuid4().hex[:6].upper()}",
            "post_id": post_id,
            "platform": platform,
            "action": "check_platform_rules",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("crt.escalate_distribution_issue")
    def escalate_distribution_issue(self, post_id: str, issue: str) -> dict:
        """Escalate a distribution issue."""
        return {
            "record_id": f"TAR-{uuid.uuid4().hex[:6].upper()}",
            "post_id": post_id,
            "issue": issue,
            "action": "escalate_distribution_issue",
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
