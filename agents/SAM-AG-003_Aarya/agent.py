"""Aarya — AI Chief Creative Officer (SAM-AG-003).

Phase 1 P1 agent #2. Head of creative & content production: translates approved
briefs into on-brand, compliant, publish-ready content. Owns content strategy,
production QA, and brand governance.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Aarya(BaseAgent):
    """AI Chief Creative Officer (Creative & Content)."""

    canonical_id = "SAM-AG-003"
    name = "Aarya"
    designation = "AI Chief Creative Officer"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.set_strategy": True,
        "crt.assign_package": True,
        "crt.approve_qa": True,
        "crt.reject_content": True,
        "crt.build_calendar": True,
        "crt.escalate_blocker": True,
        "crt.brand_check": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Aarya, the AI Chief Creative Officer (AI CCO) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-003 · Position: CRT-001 · Legacy: SAM-EX-003
- You report to Arjun (AI CEO, SAM-AG-001). You do NOT report to any other agent.
- You own creative strategy, content production and brand quality.
- Your technical custodian is Sutra. Your independent evaluator is Satya.
  Satya does NOT report to you and you cannot alter Satya's findings.

YOUR MISSION
Own creative strategy, content production and brand quality. Translate approved
briefs into on-brand, compliant, publish-ready content. Every content deliverable
must be verified for brand consistency and healthcare compliance before approval.

YOUR FIVE REGISTERS
1. Content Strategy Register — pillars, themes, messaging, audience per client
2. Content Calendar Register — editorial calendar: platform, format, deadline, owner
3. Content Package Register — type, specialist, status, deadline, brand version
4. Brand Governance Register — guidelines, tone, visual identity, compliance rules
5. Creative QA Register — every QA review: findings, revisions, closure evidence

HARD RULES — NEVER VIOLATE
1. Never publish content without human/client approval.
2. Never change approved client scope — route to human.
3. Never suppress a content quality failure to improve your score.
4. Healthcare clients: avoid unsupported clinical claims or guarantees.
5. Satya's findings are immutable to you — read-only.
6. Every content package has an owner, deadline and evidence.
7. If the local model is down, report it honestly — do not fake output."""

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
                text=f"[MODEL UNAVAILABLE] {e}. Aarya cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="crt.content",
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
    # Aarya's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("crt.set_strategy")
    def create_content_strategy(
        self,
        client_id: str,
        pillars: dict,
        themes: dict,
        messaging: dict,
        audience: dict,
    ) -> dict:
        """Create a content strategy for a client."""
        strategy_id = f"STRAT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "strategy_id": strategy_id,
            "client_id": client_id,
            "pillars": pillars,
            "themes": themes,
            "messaging": messaging,
            "audience": audience,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.build_calendar")
    def build_content_calendar(
        self,
        client_id: str,
        period_start: str,
        period_end: str,
        items: list,
    ) -> dict:
        """Build an editorial calendar."""
        calendar_id = f"CAL-{uuid.uuid4().hex[:6].upper()}"
        return {
            "calendar_id": calendar_id,
            "client_id": client_id,
            "period_start": period_start,
            "period_end": period_end,
            "items": items,
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.assign_package")
    def assign_content_package(
        self,
        calendar_id: str,
        title: str,
        type: str,
        specialist: str,
        deadline: str | None = None,
    ) -> dict:
        """Assign a content package to a specialist."""
        package_id = f"CPKG-{uuid.uuid4().hex[:6].upper()}"
        return {
            "package_id": package_id,
            "calendar_id": calendar_id,
            "title": title,
            "type": type,
            "specialist": specialist,
            "deadline": deadline,
            "status": "allocated",
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.brand_check")
    def brand_compliance_check(
        self,
        package_id: str,
        content: str,
        brand_guidelines: dict,
    ) -> dict:
        """Check content against brand guidelines."""
        issues = []
        # Simplified brand check
        if not content.strip():
            issues.append("EMPTY_CONTENT")
        return {
            "package_id": package_id,
            "compliant": len(issues) == 0,
            "issues": issues,
            "brand_version": brand_guidelines.get("version", "1.0"),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.approve_qa")
    def qa_review(
        self,
        package_id: str,
        reviewer: str,
        findings: dict,
    ) -> dict:
        """Run a QA review on a content package."""
        review_id = f"QA-{uuid.uuid4().hex[:6].upper()}"
        passed = len(findings.get("critical", [])) == 0
        return {
            "review_id": review_id,
            "package_id": package_id,
            "reviewer": reviewer,
            "findings": findings,
            "passed": passed,
            "status": "resolved" if passed else "open",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.reject_content")
    def reject_content(
        self,
        package_id: str,
        reason: str,
        required_revisions: list,
    ) -> dict:
        """Reject non-compliant content."""
        return {
            "package_id": package_id,
            "rejected": True,
            "reason": reason,
            "required_revisions": required_revisions,
            "status": "blocked",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_blocker")
    def escalate_blocker(
        self,
        package_id: str,
        severity: str,
        description: str,
        affected_clients: list,
    ) -> dict:
        """Escalate a content blocker to human Board."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "package_id": package_id,
            "severity": severity,
            "description": description,
            "affected_clients": affected_clients,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_strategies(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List content strategies (read-only)."""
        return {
            "strategies": [],
            "count": 0,
            "filter": {"client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_calendars(
        self,
        client_id: str | None = None,
    ) -> dict:
        """List content calendars (read-only)."""
        return {
            "calendars": [],
            "count": 0,
            "filter": {"client_id": client_id},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_packages(
        self,
        calendar_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List content packages (read-only)."""
        return {
            "packages": [],
            "count": 0,
            "filter": {"calendar_id": calendar_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_brand_guidelines(
        self,
        client_id: str,
    ) -> dict:
        """Get brand guidelines for a client (read-only)."""
        return {
            "client_id": client_id,
            "guidelines": {},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_qa_reviews(
        self,
        package_id: str | None = None,
    ) -> dict:
        """List QA reviews (read-only)."""
        return {
            "reviews": [],
            "count": 0,
            "filter": {"package_id": package_id},
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
