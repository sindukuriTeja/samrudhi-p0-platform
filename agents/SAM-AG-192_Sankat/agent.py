"""Sankat — Critical Risk & Escalation (SAM-AG-192 · GOV-018).

Stage 1C assurance agent (P0). Service-first agent: runs in code only and never calls the model.
Detect critical risks and raise them to humans fast: critical incidents go to Satya and
the Board. [PDF 01A.11 · GOV-018 Critical Risk & Escalation Monitoring; GOV-P20,
GOV-P21]
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
class Sankat(BaseAgent):
    """Critical Risk & Escalation."""

    canonical_id = "SAM-AG-192"
    name = "Sankat"
    designation = "Critical Risk & Escalation"
    agent_type = "service-first"

    AUTHORITY = {
        "gov.raise_critical_alert": True,
        "gov.classify_risk": True,
        "gov.track_escalation": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "raise_critical_alert": "gov.raise_critical_alert",
        "classify_risk": "gov.classify_risk",
        "track_escalation": "gov.track_escalation",
    }

    SYSTEM_PROMPT = """You are Sankat, Critical Risk & Escalation (SAM-AG-192 · GOV-018) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-192 · Position: GOV-018 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Detect critical risks and raise them to humans fast: critical incidents go to Satya and the
Board. [PDF 01A.11 · GOV-018 Critical Risk & Escalation Monitoring; GOV-P20, GOV-P21]

YOUR REGISTERS
1. Critical Alert Register — alert, source, severity, routed to, status

AUTHORITY MATRIX
gov.raise_critical_alert · gov.classify_risk · gov.track_escalation
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
        action = kwargs.get("action", "escalate")
        if action not in self.TOOLS:
            return AgentResult(
                text=(f"Sankat is a service-first agent and runs in code only. "
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
                event_type="gov.critical",
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
    # Sankat's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.raise_critical_alert")
    def raise_critical_alert(self, source: str, summary: str, severity: str = "S1", tenant_id: str = "DEMO-HEALTHCARE-01") -> dict:
        """Raise a critical (S1/S2) alert to the Board."""
        if severity not in ("S1", "S2"):
            raise ValueError("Sankat only raises critical alerts (S1 or S2).")
        alert_id = f"CRIT-{uuid.uuid4().hex[:6].upper()}"
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.critical_alert", source_agent=self.canonical_id, target_agent="all",
                payload={"alert_id": alert_id, "source": source, "summary": summary,
                         "route_to": "HUMAN-BOARD"},
                tenant_id=tenant_id, severity=severity,
            ))
            published = True
        except Exception:
            published = False
        return {
            "alert_id": alert_id,
            "source": source,
            "summary": summary,
            "severity": severity,
            "routed_to": "HUMAN-BOARD",
            "published": published,
            "status": "raised",
            "raised_at": _now(),
        }

    @authority_guard("gov.classify_risk")
    def classify_risk(self, risk: str, severity: str) -> dict:
        """Classify a risk."""
        return {
            "record_id": f"SAN-{uuid.uuid4().hex[:6].upper()}",
            "risk": risk,
            "severity": severity,
            "action": "classify_risk",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.track_escalation")
    def track_escalation(self, alert_id: str, status: str) -> dict:
        """Track an escalation."""
        return {
            "record_id": f"SAN-{uuid.uuid4().hex[:6].upper()}",
            "alert_id": alert_id,
            "status": status,
            "action": "track_escalation",
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
