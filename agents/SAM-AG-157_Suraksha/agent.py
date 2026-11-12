"""Suraksha — Security and Reliability Lead (SAM-AG-157).

Stage 1B service-first agent. Access control, security rules, incident response.
Service-first: security policy enforcement (no LLM).
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Suraksha(BaseAgent):
    """Security and Reliability Lead."""

    canonical_id = "SAM-AG-157"
    name = "Suraksha"
    designation = "Security and Reliability Lead"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.enforce_security": True,
        "tec.log_incident": True,
        "tec.block_access": True,
        "gov.approve_certification": False,
    }

    SECURITY_RULES = [
        "No credential storage in plaintext",
        "All agent calls logged to execution_log",
        "Tenant isolation enforced on every query",
        "Privileged access requires human approval",
        "Incidents S1/S2 escalate to human within SLA",
    ]

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._incidents = []

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "check")
        if action == "check":
            text = "Security Policy:\n" + "\n".join(f"  - {r}" for r in self.SECURITY_RULES)
        elif action == "incident":
            sev = kwargs.get("severity", "S3")
            desc = kwargs.get("description", task)
            inc_id = f"INC-{len(self._incidents)+1:04d}"
            self._incidents.append({"id": inc_id, "severity": sev, "description": desc, "at": datetime.now(timezone.utc).isoformat()})
            text = f"Logged incident {inc_id} (severity {sev})"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.log_incident")
    def log_incident(self, severity: str, description: str) -> dict:
        inc_id = f"INC-{len(self._incidents)+1:04d}"
        record = {"id": inc_id, "severity": severity, "description": description, "at": datetime.now(timezone.utc).isoformat()}
        self._incidents.append(record)
        return record

    @authority_guard("tec.enforce_security")
    def check_policy(self, action: str) -> dict:
        """Deterministic security policy check."""
        violations = []
        if "plaintext" in action.lower() and "credential" in action.lower():
            violations.append("No credential storage in plaintext")
        if "unlogged" in action.lower():
            violations.append("All agent calls must be logged")
        return {"action": action, "compliant": not violations, "violations": violations}

    def route_for_approval(
        self,
        request_type: str,
        details: dict,
    ) -> dict:
        """Route a request outside delegated authority to human approval."""
        import uuid as _uuid
        return {
            "request_id": f"REQ-{_uuid.uuid4().hex[:6].upper()}",
            "request_type": request_type,
            "details": details,
            "status": "pending_human_approval",
            "routed_at": datetime.now(timezone.utc).isoformat(),
        }
