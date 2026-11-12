"""Samiksha — Client Review Agent (SAM-AG-053).

Phase 3 Client Experience agent. Owns client review: collect feedback, analyze
feedback, report review status, and escalation of review issues. Reports to
Mitra (SAM-AG-004).
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Samiksha(BaseAgent):
    """Client Review Agent."""

    canonical_id = "SAM-AG-053"
    name = "Samiksha"
    designation = "Client Review Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "cex.review_client": True,
        "cex.collect_feedback": True,
        "cex.analyze_feedback": True,
        "cex.report_review": True,
        "cex.escalate_review_issue": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Samiksha, the Client Review Agent (SAM-AG-053 · CEX-007) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-053 · Position: CEX-007 · Legacy: SAM-EX-053
- You report to Mitra (AI Chief Client Experience Officer, SAM-AG-004).
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own client review: collect feedback, analyze feedback, report review status,
and escalate review issues. Every review must be honest, comprehensive and
actionable. Never fabricate feedback or suppress negative sentiment.

YOUR FIVE REGISTERS
1. Review Register — review events, type, status per client
2. Feedback Collection Register — surveys, responses, ratings
3. Feedback Analysis Register — sentiment, themes, action items
4. Review Report Register — summary reports, trends, insights
5. Review Escalation Register — critical feedback, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate feedback or manipulate sentiment analysis. Missing = "unavailable".
2. Never suppress negative feedback to improve satisfaction scores.
3. Never alter client responses — raw feedback is immutable.
4. Respect tenant isolation — never cross-client feedback leakage.
5. Satya's findings are immutable to you — read-only.
6. Every review has a timestamp and documented findings.
7. If the local model is down, report it honestly — do not fake output."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Samiksha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="cex.review",
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
    # Samiksha's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("cex.review_client")
    def review_client(
        self,
        client_id: str,
        review_type: str,
        period: str,
    ) -> dict:
        """Initiate a client review."""
        review_id = f"REV-{uuid.uuid4().hex[:6].upper()}"
        return {
            "review_id": review_id,
            "client_id": client_id,
            "review_type": review_type,
            "period": period,
            "status": "initiated",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.collect_feedback")
    def collect_feedback(
        self,
        client_id: str,
        source: str,
        feedback_type: str,
        responses: dict,
    ) -> dict:
        """Collect feedback from a client."""
        feedback_id = f"FB-{uuid.uuid4().hex[:6].upper()}"
        return {
            "feedback_id": feedback_id,
            "client_id": client_id,
            "source": source,
            "feedback_type": feedback_type,
            "responses": responses,
            "status": "collected",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.analyze_feedback")
    def analyze_feedback(
        self,
        feedback_id: str,
        sentiment: str,
        themes: list,
        action_items: list,
    ) -> dict:
        """Analyze collected feedback."""
        analysis_id = f"ANL-{uuid.uuid4().hex[:6].upper()}"
        return {
            "analysis_id": analysis_id,
            "feedback_id": feedback_id,
            "sentiment": sentiment,
            "themes": themes,
            "action_items": action_items,
            "status": "analyzed",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.report_review")
    def report_review(
        self,
        client_id: str,
        period: str,
        findings: list,
        recommendations: list,
    ) -> dict:
        """Generate a client review report."""
        report_id = f"RPT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "report_id": report_id,
            "client_id": client_id,
            "period": period,
            "findings": findings,
            "recommendations": recommendations,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("cex.escalate_review_issue")
    def escalate_review_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
        critical_findings: list,
    ) -> dict:
        """Escalate a review issue to human."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "critical_findings": critical_findings,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reviews(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List review records (read-only)."""
        return {
            "reviews": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_feedback(
        self,
        client_id: str,
    ) -> dict:
        """Get feedback for a client (read-only)."""
        return {
            "client_id": client_id,
            "feedback": [],
            "count": 0,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_analysis(
        self,
        feedback_id: str,
    ) -> dict:
        """Get feedback analysis (read-only)."""
        return {
            "feedback_id": feedback_id,
            "analysis": {},
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
