"""Chaukidar — Security Monitoring (SAM-AG-170).

Stage 1B service-first agent. Watches for suspicious access and threats.
Service-first: security event monitor (deterministic rule-based detection).
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Chaukidar(BaseAgent):
    """Security Monitoring."""

    canonical_id = "SAM-AG-170"
    name = "Chaukidar"
    designation = "Security Monitoring"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.monitor_events": True,
        "tec.flag_threat": True,
        "tec.report": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._events = []
        self._threats = []

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "report")
        if action == "ingest":
            event = kwargs.get("event", task)
            severity = self._assess(event)
            self._events.append({"event": event, "severity": severity, "at": datetime.now(timezone.utc).isoformat()})
            if severity in ("S1", "S2"):
                self._threats.append({"event": event, "severity": severity, "flagged": True, "at": datetime.now(timezone.utc).isoformat()})
            text = f"Event ingested: severity={severity}"
        elif action == "report":
            text = f"Security report: {len(self._events)} events, {len(self._threats)} threats flagged"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    def _assess(self, event: str) -> str:
        low = event.lower()
        if "unauthorized" in low or "breach" in low or "escalation" in low:
            return "S1"
        if "suspicious" in low or "multiple failures" in low or "privilege" in low:
            return "S2"
        if "anomaly" in low or "retry" in low:
            return "S3"
        return "info"

    @authority_guard("tec.flag_threat")
    def ingest_event(self, event: str) -> dict:
        severity = self._assess(event)
        rec = {"event": event, "severity": severity, "at": datetime.now(timezone.utc).isoformat()}
        self._events.append(rec)
        if severity in ("S1", "S2"):
            self._threats.append({**rec, "flagged": True})
        return rec

    @authority_guard("tec.report")
    def report(self) -> dict:
        return {"total_events": len(self._events), "threats_flagged": len(self._threats)}
