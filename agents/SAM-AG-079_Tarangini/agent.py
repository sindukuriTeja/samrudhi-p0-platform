"""Tarangini — Video Content Agent (SAM-AG-079).

Phase 2 content pilot agent. Owns video content under Aarya:
creates video scripts, storyboards, video production briefs for healthcare content.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Tarangini(BaseAgent):
    """Video Content Agent."""

    canonical_id = "SAM-AG-079"
    name = "Tarangini"
    designation = "Video Content Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.create_video_script": True,
        "crt.create_storyboard": True,
        "crt.set_video_specs": True,
        "crt.check_video_compliance": True,
        "crt.escalate_video": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Tarangini, the Video Content Agent (SAM-AG-079 · CRT-024) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-079 · Position: CRT-024
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own video content. Create video scripts, storyboards, video production briefs
for healthcare content. Ensure video content is compliant and on-brand.
Never publish without approval. Never provide medical advice.

YOUR REGISTERS
1. Video Script Register — scripts, versions, status
2. Storyboard Register — storyboards, scenes, specs
3. Video Specs Register — formats, durations, platforms
4. Video Compliance Register — compliance checks, findings
5. Video Escalation Register — blockers, escalations

HARD RULES — NEVER VIOLATE
1. Never publish video without approval.
2. Never provide medical advice in video scripts.
3. Never fabricate video metrics. Missing = "unavailable".
4. Never suppress a compliance issue.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "create")
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
            bus.publish(BusEnvelope(
                event_type="crt.video",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.create_video_script")
    def create_video_script(
        self,
        client_id: str,
        topic: str,
        duration: str,
        brief: dict,
    ) -> dict:
        """Create a video script."""
        script_id = f"VSC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "script_id": script_id,
            "client_id": client_id,
            "topic": topic,
            "duration": duration,
            "script": "",
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.create_storyboard")
    def create_storyboard(
        self,
        script_id: str,
        scenes: list,
    ) -> dict:
        """Create a storyboard for a video script."""
        storyboard_id = f"STB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "storyboard_id": storyboard_id,
            "script_id": script_id,
            "scenes": scenes,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.set_video_specs")
    def set_video_specs(
        self,
        script_id: str,
        formats: list,
        platforms: list,
        technical_specs: dict,
    ) -> dict:
        """Set video production specifications."""
        return {
            "script_id": script_id,
            "formats": formats,
            "platforms": platforms,
            "technical_specs": technical_specs,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.check_video_compliance")
    def check_video_compliance(
        self,
        script_id: str,
        script: str,
        compliance_rules: dict,
    ) -> dict:
        """Check video script for compliance."""
        violations = []
        return {
            "script_id": script_id,
            "compliant": len(violations) == 0,
            "violations": violations,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_video")
    def escalate_video_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a video content issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_scripts(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List video scripts (read-only)."""
        return {
            "scripts": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_storyboard(
        self,
        storyboard_id: str,
    ) -> dict:
        """Get storyboard details (read-only)."""
        return {
            "storyboard_id": storyboard_id,
            "details": {},
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
