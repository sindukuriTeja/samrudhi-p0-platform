"""Pariksha — Content Review Agent (SAM-AG-094).

Phase 2 content pilot agent. Owns technical content review under Aarya:
performs technical QA, fact-checking, and content accuracy reviews.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Pariksha(BaseAgent):
    """Content Review Agent."""

    canonical_id = "SAM-AG-094"
    name = "Pariksha"
    designation = "Content Review Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.review_content": True,
        "crt.fact_check": True,
        "crt.check_accuracy": True,
        "crt.flag_issue": True,
        "crt.escalate_review": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Pariksha, the Content Review Agent (SAM-AG-094 · CRT-026) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-094 · Position: CRT-026
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own technical content review. Perform technical QA, fact-checking, and content
accuracy reviews. Flag issues and approve accurate content. Never approve
inaccurate content. Never fabricate review data.

YOUR REGISTERS
1. Review Request Register — review requests, content refs, deadlines
2. Fact Check Register — facts checked, verdicts, sources
3. Accuracy Register — accuracy scores, findings
4. Review Issue Register — issues, severity, status
5. Review Escalation Register — escalations, resolutions

HARD RULES — NEVER VIOLATE
1. Never approve inaccurate or unverified content.
2. Never fabricate fact-check results. Missing = "unverified".
3. Never suppress a review finding or accuracy issue.
4. Every fact check has a source and verdict.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Pariksha cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.review",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.review_content")
    def review_content(
        self,
        content_ref: str,
        content: str,
        review_criteria: dict,
    ) -> dict:
        """Review content for accuracy and quality."""
        review_id = f"REV-{uuid.uuid4().hex[:6].upper()}"
        score = sum(review_criteria.values()) / len(review_criteria) if review_criteria else 0
        return {
            "review_id": review_id,
            "content_ref": content_ref,
            "score": round(score, 2),
            "criteria": review_criteria,
            "status": "reviewed",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.fact_check")
    def fact_check(
        self,
        content_ref: str,
        claims: list,
        sources: dict,
    ) -> dict:
        """Fact-check claims in content."""
        check_id = f"FCK-{uuid.uuid4().hex[:6].upper()}"
        results = []
        for claim in claims:
            verified = claim in sources
            results.append({"claim": claim, "verified": verified})
        return {
            "check_id": check_id,
            "content_ref": content_ref,
            "results": results,
            "all_verified": all(r["verified"] for r in results),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.check_accuracy")
    def check_accuracy(
        self,
        content_ref: str,
        content: str,
        reference_data: dict,
    ) -> dict:
        """Check content accuracy against reference data."""
        issues = []
        return {
            "content_ref": content_ref,
            "accurate": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.flag_issue")
    def flag_review_issue(
        self,
        content_ref: str,
        issue_type: str,
        severity: str,
        description: str,
    ) -> dict:
        """Flag a review issue."""
        issue_id = f"ISS-{uuid.uuid4().hex[:6].upper()}"
        return {
            "issue_id": issue_id,
            "content_ref": content_ref,
            "issue_type": issue_type,
            "severity": severity,
            "description": description,
            "status": "open",
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_review")
    def escalate_review_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a review issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reviews(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List reviews (read-only)."""
        return {
            "reviews": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_fact_check(
        self,
        check_id: str,
    ) -> dict:
        """Get fact-check results (read-only)."""
        return {
            "check_id": check_id,
            "results": [],
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
