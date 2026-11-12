"""Gopniya — Privacy & Confidentiality (SAM-AG-187 · GOV-013).

Stage 1C assurance agent (P0). Service-first agent: runs in code only and never calls the model.
Assure privacy and confidentiality: check that content and runs contain no personal data
and no other client's information, and test client-data isolation. [PDF 01A.11 · GOV-013
Data Privacy & Confidentiality Assurance; GOV-P18, GOV-P19]
Reports to Satya (Chief Assurance Agent, SAM-AG-010).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Gopniya(BaseAgent):
    """Privacy & Confidentiality."""

    canonical_id = "SAM-AG-187"
    name = "Gopniya"
    designation = "Privacy & Confidentiality"
    agent_type = "service-first"

    AUTHORITY = {
        "gov.check_privacy": True,
        "gov.record_isolation_test": True,
        "gov.escalate_privacy_breach": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "check_privacy": "gov.check_privacy",
        "record_isolation_test": "gov.record_isolation_test",
        "escalate_privacy_breach": "gov.escalate_privacy_breach",
    }

    SYSTEM_PROMPT = """You are Gopniya, Privacy & Confidentiality (SAM-AG-187 · GOV-013) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-187 · Position: GOV-013 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Assure privacy and confidentiality: check that content and runs contain no personal data and no
other client's information, and test client-data isolation. [PDF 01A.11 · GOV-013 Data Privacy &
Confidentiality Assurance; GOV-P18, GOV-P19]

YOUR REGISTERS
1. Privacy Check Register — content, findings, result
2. Isolation Test Register — tenant, test, result

AUTHORITY MATRIX
gov.check_privacy · gov.record_isolation_test · gov.escalate_privacy_breach
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. You are independent: you never produce the content or work you assess.
5. Never certify an agent — certification needs Satya and a human (gov.certify is denied).
6. Report critical risks to Satya and, through Sankat, to the Board.
7. You never call the model; every result comes from code."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        """Service-first: runs one of its tools in code. Never calls the model."""
        import json
        action = kwargs.get("action", "privacy")
        if action not in self.TOOLS:
            return AgentResult(
                text=(f"Gopniya is a service-first agent and runs in code only. "
                      f"Supported actions: {', '.join(self.TOOLS)}."),
                agent_id=self.canonical_id, tokens_used=0, status="completed",
            )
        try:
            result = getattr(self, action)(**kwargs.get("params", {}))
            text, status = json.dumps(result, default=str), "completed"
        except Exception as e:
            text, status = f"{action} failed: {e}", "failed"
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.privacy",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task, "status": status},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status=status)

    # ------------------------------------------------------------------
    # Gopniya's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.check_privacy")
    def check_privacy(self, content: str, other_client_names: list = None) -> dict:
        """Find personal data or other-client names."""
        import re
        text = content or ""
        findings = []
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            findings.append("EMAIL_ADDRESS")
        if re.search(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{9}(?!\d)", text):
            findings.append("PHONE_NUMBER")
        if re.search(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)", text):
            findings.append("ID_NUMBER")
        for name in other_client_names or []:
            if name and name.lower() in text.lower():
                findings.append(f"OTHER_CLIENT:{name}")
        return {
            "check_id": f"PRV-{uuid.uuid4().hex[:6].upper()}",
            "findings": findings,
            "passed": not findings,
            "status": "pass" if not findings else "block",
            "checked_at": _now(),
        }

    @authority_guard("gov.record_isolation_test")
    def record_isolation_test(self, tenant_id: str, passed: bool) -> dict:
        """Record a client-isolation test."""
        return {
            "record_id": f"GOP-{uuid.uuid4().hex[:6].upper()}",
            "tenant_id": tenant_id,
            "passed": passed,
            "action": "record_isolation_test",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_privacy_breach")
    def escalate_privacy_breach(self, content_ref: str, finding: str) -> dict:
        """Escalate a privacy breach."""
        return {
            "record_id": f"GOP-{uuid.uuid4().hex[:6].upper()}",
            "content_ref": content_ref,
            "finding": finding,
            "action": "escalate_privacy_breach",
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
