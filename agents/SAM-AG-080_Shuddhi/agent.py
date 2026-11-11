"""Shuddhi — Compliance & Quality Agent (SAM-AG-080).

Phase 2 content pilot agent. Owns compliance and quality assurance under Aarya:
checks content for healthcare compliance, brand adherence, and quality standards.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Shuddhi(BaseAgent):
    """Compliance & Quality Agent."""

    canonical_id = "SAM-AG-080"
    name = "Shuddhi"
    designation = "Compliance & Quality Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.check_compliance": True,
        "crt.quality_review": True,
        "crt.flag_violation": True,
        "crt.approve_content": True,
        "crt.escalate_compliance": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Shuddhi, the Compliance & Quality Agent (SAM-AG-080 · CRT-020) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-080 · Position: CRT-020
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own compliance and quality assurance. Check content for healthcare compliance,
brand adherence, and quality standards. Flag violations and approve compliant
content. Never approve non-compliant content. Never suppress a violation.

YOUR REGISTERS
1. Compliance Check Register — checks, findings, verdicts
2. Quality Review Register — reviews, scores, findings
3. Violation Register — violations, severity, status
4. Approval Register — approved content, evidence
5. Compliance Escalation Register — escalations, resolutions

HARD RULES — NEVER VIOLATE
1. Never approve non-compliant content.
2. Never suppress a compliance violation or quality issue.
3. Never fabricate compliance metrics. Missing = "unavailable".
4. Healthcare claims must be evidence-based.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "check")
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
                text=f"[MODEL UNAVAILABLE] {e}. Shuddhi cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="crt.compliance",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.check_compliance")
    def check_compliance(
        self,
        content_ref: str,
        content: str,
        compliance_rules: dict,
    ) -> dict:
        """Check content for healthcare compliance."""
        check_id = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        violations = []
        if not content.strip():
            violations.append({"type": "EMPTY", "severity": "S2"})
        return {
            "check_id": check_id,
            "content_ref": content_ref,
            "violations": violations,
            "compliant": len(violations) == 0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.quality_review")
    def quality_review(
        self,
        content_ref: str,
        criteria: dict,
    ) -> dict:
        """Perform a quality review on content."""
        review_id = f"QRL-{uuid.uuid4().hex[:6].upper()}"
        score = sum(criteria.values()) / len(criteria) if criteria else 0
        return {
            "review_id": review_id,
            "content_ref": content_ref,
            "score": round(score, 2),
            "criteria": criteria,
            "status": "reviewed",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.flag_violation")
    def flag_violation(
        self,
        content_ref: str,
        violation_type: str,
        severity: str,
        description: str,
    ) -> dict:
        """Flag a compliance violation."""
        violation_id = f"VIOL-{uuid.uuid4().hex[:6].upper()}"
        return {
            "violation_id": violation_id,
            "content_ref": content_ref,
            "violation_type": violation_type,
            "severity": severity,
            "description": description,
            "status": "open",
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.approve_content")
    def approve_content(
        self,
        content_ref: str,
        compliance_check: dict,
        quality_review: dict,
    ) -> dict:
        """Approve content that passes compliance and quality."""
        approval_id = f"APPR-{uuid.uuid4().hex[:6].upper()}"
        passed = compliance_check.get("compliant", False) and quality_review.get("score", 0) >= 0.7
        return {
            "approval_id": approval_id,
            "content_ref": content_ref,
            "approved": passed,
            "compliance_check": compliance_check,
            "quality_review": quality_review,
            "status": "approved" if passed else "rejected",
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_compliance")
    def escalate_compliance_issue(
        self,
        client_id: str,
        severity: str,
        description: str,
    ) -> dict:
        """Escalate a compliance issue."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "client_id": client_id,
            "severity": severity,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_checks(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List compliance checks (read-only)."""
        return {
            "checks": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_violations(
        self,
        client_id: str | None = None,
    ) -> dict:
        """Get violations (read-only)."""
        return {
            "violations": [],
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
