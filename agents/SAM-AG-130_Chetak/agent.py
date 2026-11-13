"""Chetak — Anomaly Detection (SAM-AG-130 · DAT-016).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Detect anomalies in the numbers — unusual jumps or drops — prioritise the alerts and
give early warnings. [PDF 01A.08 · DAT-016 Anomaly & Early Warning Intelligence; process
DAT-P25]
Reports to Medha (AI CDO, SAM-AG-009).
Identity from the PDF canonical registry (Document 01C); role from the department register.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@register_agent
class Chetak(BaseAgent):
    """Anomaly Detection."""

    canonical_id = "SAM-AG-130"
    name = "Chetak"
    designation = "Anomaly Detection"
    agent_type = "thinking"

    AUTHORITY = {
        "dat.detect_anomaly": True,
        "dat.prioritise_alert": True,
        "dat.record_alert": True,
        "dat.acknowledge_alert": True,
        "dat.escalate_critical_anomaly": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "detect_anomaly": "dat.detect_anomaly",
        "prioritise_alert": "dat.prioritise_alert",
        "record_alert": "dat.record_alert",
        "acknowledge_alert": "dat.acknowledge_alert",
        "escalate_critical_anomaly": "dat.escalate_critical_anomaly",
    }

    SYSTEM_PROMPT = """You are Chetak, Anomaly Detection (SAM-AG-130 · DAT-016) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-130 · Position: DAT-016 · Department: Analytics, Intelligence & Reporting
- You report to Medha (AI CDO, SAM-AG-009).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Detect anomalies in the numbers — unusual jumps or drops — prioritise the alerts and give early
warnings. [PDF 01A.08 · DAT-016 Anomaly & Early Warning Intelligence; process DAT-P25]

YOUR REGISTERS
1. Anomaly Register — metric, baseline, latest, change, status
2. Alert Register — alert, priority, acknowledged

AUTHORITY MATRIX
dat.detect_anomaly · dat.prioritise_alert · dat.record_alert · dat.acknowledge_alert · dat.escalate_critical_anomaly
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never hide an anomaly; false alarms are logged, not deleted.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "detect")
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
                text=f"[MODEL UNAVAILABLE] {e}. Chetak cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="dat.anomaly",
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
    # Chetak's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("dat.detect_anomaly")
    def detect_anomaly(self, metric: str, values: list, threshold_pct: float = 30.0) -> dict:
        """Compare the latest value with the baseline."""
        vals = [float(v) for v in (values or [])]
        if len(vals) < 3:
            return {"metric": metric, "status": "unavailable", "reason": "need at least 3 values",
                    "checked_at": _now()}
        base = sum(vals[:-1]) / len(vals[:-1])
        latest = vals[-1]
        change = 0.0 if base == 0 else round((latest - base) / abs(base) * 100, 1)
        anomaly = abs(change) >= threshold_pct
        return {
            "metric": metric,
            "baseline": round(base, 4),
            "latest": latest,
            "change_pct": change,
            "anomaly": anomaly,
            "status": "alert" if anomaly else "normal",
            "checked_at": _now(),
        }

    @authority_guard("dat.prioritise_alert")
    def prioritise_alert(self, alert_id: str, priority: str) -> dict:
        """Prioritise an alert."""
        return {
            "record_id": f"CHE-{uuid.uuid4().hex[:6].upper()}",
            "alert_id": alert_id,
            "priority": priority,
            "action": "prioritise_alert",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.record_alert")
    def record_alert(self, metric: str, summary: str) -> dict:
        """Record an alert."""
        return {
            "record_id": f"CHE-{uuid.uuid4().hex[:6].upper()}",
            "metric": metric,
            "summary": summary,
            "action": "record_alert",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.acknowledge_alert")
    def acknowledge_alert(self, alert_id: str, by: str) -> dict:
        """Acknowledge an alert."""
        return {
            "record_id": f"CHE-{uuid.uuid4().hex[:6].upper()}",
            "alert_id": alert_id,
            "by": by,
            "action": "acknowledge_alert",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("dat.escalate_critical_anomaly")
    def escalate_critical_anomaly(self, metric: str, summary: str) -> dict:
        """Escalate a critical anomaly."""
        return {
            "record_id": f"CHE-{uuid.uuid4().hex[:6].upper()}",
            "metric": metric,
            "summary": summary,
            "action": "escalate_critical_anomaly",
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
