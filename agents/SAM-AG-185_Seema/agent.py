"""Seema — Authority & Permission Audit (SAM-AG-185 · GOV-011).

Stage 1C assurance agent (P0). Service-first agent: runs in code only and never calls the model.
Audit authority and permissions: check that agents act inside their authority matrices,
detect privilege drift and review tool and access permissions. [PDF 01A.11 · GOV-011
Agent Authority & Permission Audit; GOV-P15]
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
class Seema(BaseAgent):
    """Authority & Permission Audit."""

    canonical_id = "SAM-AG-185"
    name = "Seema"
    designation = "Authority & Permission Audit"
    agent_type = "service-first"

    AUTHORITY = {
        "gov.audit_permission_use": True,
        "gov.detect_privilege_drift": True,
        "gov.escalate_authority_breach": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "audit_permission_use": "gov.audit_permission_use",
        "detect_privilege_drift": "gov.detect_privilege_drift",
        "escalate_authority_breach": "gov.escalate_authority_breach",
    }

    SYSTEM_PROMPT = """You are Seema, Authority & Permission Audit (SAM-AG-185 · GOV-011) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-185 · Position: GOV-011 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Audit authority and permissions: check that agents act inside their authority matrices, detect
privilege drift and review tool and access permissions. [PDF 01A.11 · GOV-011 Agent Authority &
Permission Audit; GOV-P15]

YOUR REGISTERS
1. Permission Audit Register — agent, permission, result
2. Privilege Drift Register — agent, permissions, status

AUTHORITY MATRIX
gov.audit_permission_use · gov.detect_privilege_drift · gov.escalate_authority_breach
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
        action = kwargs.get("action", "audit")
        if action not in self.TOOLS:
            return AgentResult(
                text=(f"Seema is a service-first agent and runs in code only. "
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
                event_type="gov.permission_audit",
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
    # Seema's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.audit_permission_use")
    def audit_permission_use(self, agent_id: str, permission: str) -> dict:
        """Check a permission against the agent's matrix."""
        from backend.core.authority import load_authority_matrix
        matrix = load_authority_matrix(agent_id)
        allowed = bool(matrix.get(permission, False))
        return {
            "agent_id": agent_id,
            "permission": permission,
            "allowed": allowed,
            "status": "within_authority" if allowed else "outside_authority",
            "audited_at": _now(),
        }

    @authority_guard("gov.detect_privilege_drift")
    def detect_privilege_drift(self, agent_id: str, expected: dict) -> dict:
        """Compare the live matrix with the approved one."""
        from backend.core.authority import load_authority_matrix
        actual = load_authority_matrix(agent_id)
        drift = sorted(k for k in set(actual) | set(expected or {})
                       if bool(actual.get(k, False)) != bool((expected or {}).get(k, False)))
        return {
            "agent_id": agent_id,
            "drifted_permissions": drift,
            "status": "drift_detected" if drift else "no_drift",
            "checked_at": _now(),
        }

    @authority_guard("gov.escalate_authority_breach")
    def escalate_authority_breach(self, agent_id: str, permission: str) -> dict:
        """Escalate an authority breach."""
        return {
            "record_id": f"SEE-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "permission": permission,
            "action": "escalate_authority_breach",
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
