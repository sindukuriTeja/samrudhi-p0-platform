"""Arjun — AI CEO (SAM-AG-001).

Stage 1A core thinking agent. Turns Board goals into department priorities; daily
executive brief; escalates risks. Cannot approve spend, contracts or pricing.
Build order: #2 — coordination hub for all P0 agents.
"""
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Arjun(BaseAgent):
    """AI Chief Executive Officer."""

    canonical_id = "SAM-AG-001"
    name = "Arjun"
    designation = "AI Chief Executive Officer"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.coordinate": True,
        "ops.assign_approved_task": True,
        "ops.recommend_initiative": True,
        "ops.approve_capital": False,        # recommend only
        "ops.sign_contract": False,
        "ops.commit_expenditure": False,
        "ops.approve_pricing": False,
        "gov.override_assurance": False,     # PROHIBITED
        "gov.approve_certification": False,
        "tec.change_permissions": False,     # request only via Sutra
    }

    SYSTEM_PROMPT = """You are Arjun, the AI Chief Executive Officer (AI CEO) of Samrudhi.
Canonical ID: SAM-AG-001 · Position: CEO-001. You report to the Human Board / Founder.
You coordinate eight functional executives + the independent assurance function.
Peers: Sutra (AI CTO, SAM-AG-007), Satya (Chief Assurance, SAM-AG-010),
Niyantrak (AgentOps & DWMS, SAM-AG-158).

YOUR JOB: Translate human-approved strategy into coordinated departmental execution.
Maintain five registers: Enterprise Initiative, Executive Decision, Risk & Escalation,
Cross-Department Action Tracker, Enterprise Objectives. Run four workflows:
ARJ-W01 Strategic Objective Deployment, ARJ-W02 Daily Executive Review,
ARJ-W03 Weekly Performance Review, ARJ-W04 Critical Issue Escalation.

HARD RULES — NEVER VIOLATE:
1. You cannot approve capital allocation, sign contracts, commit expenditure, or approve pricing. Recommend only.
2. You cannot override, downgrade or suppress Satya's assurance findings. Ever.
3. You cannot approve agent certifications (Satya + human governance only).
4. You cannot change agent permissions (request via Sutra).
5. You cannot fabricate KPI values. Missing data = "unavailable".
6. You cannot downgrade a critical incident to improve your own score.
7. Distinguish verified facts from assumptions in every output.
8. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "general")
        context = kwargs.get("context", {})
        prompt = f"{self.SYSTEM_PROMPT}\n\nTASK: {task}\nACTION: {action}\nCONTEXT: {json.dumps(context, default=str)}"
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Running inside async context — run in new loop
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            result = loop.run_until_complete(generate(prompt, system=self.SYSTEM_PROMPT[:500]))
            text = result.text
            tokens = result.prompt_tokens + result.response_tokens
        except Exception as e:
            return AgentResult(
                text=f"[MODEL UNAVAILABLE] {e}. Arjun cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="ceo.action",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("ops.coordinate")
    def daily_brief(self, inputs: dict) -> dict:
        """ARJ-W02: produce a daily executive brief from department inputs."""
        return {
            "type": "daily_brief",
            "period": datetime.now(timezone.utc).isoformat(),
            "generated_by": self.canonical_id,
            "inputs_received": len(inputs),
            "status": "produced",
        }

    @authority_guard("ops.recommend_initiative")
    def recommend_initiative(self, title: str, objective_ref: str) -> dict:
        """Recommend a new initiative for human approval."""
        return {
            "title": title,
            "objective_ref": objective_ref,
            "recommendation": "proposed for human approval",
            "status": "pending_approval",
        }
