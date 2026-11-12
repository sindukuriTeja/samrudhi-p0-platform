"""Nishpaksh — Independent Performance Scoring (SAM-AG-184 · GOV-010).

Stage 1C assurance agent (P0). Role agent (evaluator): may use the model to read and judge, never to produce the work it assesses.
Score agent performance consistently and reproducibly from role-specific KPIs, with
weights set by the approved method. Scores are computed in code. [PDF 01A.11 · GOV-010
Independent Performance Scoring; GOV-P10, GOV-P11]
Reports to Satya (Chief Assurance Agent, SAM-AG-010).
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
class Nishpaksh(BaseAgent):
    """Independent Performance Scoring."""

    canonical_id = "SAM-AG-184"
    name = "Nishpaksh"
    designation = "Independent Performance Scoring"
    agent_type = "role"

    AUTHORITY = {
        "gov.score_agent": True,
        "gov.benchmark_agents": True,
        "gov.escalate_performance_exception": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "score_agent": "gov.score_agent",
        "benchmark_agents": "gov.benchmark_agents",
        "escalate_performance_exception": "gov.escalate_performance_exception",
    }

    SYSTEM_PROMPT = """You are Nishpaksh, Independent Performance Scoring (SAM-AG-184 · GOV-010) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-184 · Position: GOV-010 · Department: Independent Assurance, Compliance & Agent Performance
- You report to Satya (Chief Assurance Agent, SAM-AG-010).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Score agent performance consistently and reproducibly from role-specific KPIs, with weights set
by the approved method. Scores are computed in code. [PDF 01A.11 · GOV-010 Independent
Performance Scoring; GOV-P10, GOV-P11]

YOUR REGISTERS
1. Performance Score Register — agent, period, metrics, score

AUTHORITY MATRIX
gov.score_agent · gov.benchmark_agents · gov.escalate_performance_exception
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. You are independent: you never produce the content or work you assess.
5. Never certify an agent — certification needs Satya and a human (gov.certify is denied).
6. Report critical risks to Satya and, through Sankat, to the Board.
7. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "score")
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
                text=f"[MODEL UNAVAILABLE] {e}. Nishpaksh cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="gov.scoring",
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
    # Nishpaksh's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("gov.score_agent")
    def score_agent(self, agent_id: str, metrics: dict, weights: dict = None) -> dict:
        """Weighted performance score."""
        weights = weights or {k: 1.0 for k in (metrics or {})}
        total_w = sum(weights.get(k, 0.0) for k in (metrics or {}))
        if not metrics or total_w == 0:
            return {"agent_id": agent_id, "status": "unavailable", "reason": "no metrics", "scored_at": _now()}
        score = sum(float(v) * weights.get(k, 0.0) for k, v in metrics.items()) / total_w
        return {
            "agent_id": agent_id,
            "metrics": metrics,
            "weights": weights,
            "score": round(score, 3),
            "status": "scored",
            "scored_at": _now(),
        }

    @authority_guard("gov.benchmark_agents")
    def benchmark_agents(self, agent_ids: list, period: str) -> dict:
        """Benchmark agents for a period."""
        return {
            "record_id": f"NIS-{uuid.uuid4().hex[:6].upper()}",
            "agent_ids": agent_ids,
            "period": period,
            "action": "benchmark_agents",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("gov.escalate_performance_exception")
    def escalate_performance_exception(self, agent_id: str, reason: str) -> dict:
        """Escalate a performance exception."""
        return {
            "record_id": f"NIS-{uuid.uuid4().hex[:6].upper()}",
            "agent_id": agent_id,
            "reason": reason,
            "action": "escalate_performance_exception",
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
