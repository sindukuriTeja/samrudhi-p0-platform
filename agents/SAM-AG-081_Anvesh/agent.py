"""Anvesh — Healthcare Research Agent (SAM-AG-081).

Phase 2 content pilot agent. Owns healthcare research: gathers validated
facts, source citations, and clinical references for content production.
Provides research input to copywriters under Aarya.
"""
from datetime import datetime, timezone
from typing import Any
import uuid

from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.llm import generate
from backend.core.authority import authority_guard
from backend.core.message_bus import BusEnvelope, bus


@register_agent
class Anvesh(BaseAgent):
    """Healthcare Research Agent."""

    canonical_id = "SAM-AG-081"
    name = "Anvesh"
    designation = "Healthcare Research Agent"
    agent_type = "thinking"

    AUTHORITY = {
        "crt.research_topic": True,
        "crt.gather_facts": True,
        "crt.cite_sources": True,
        "crt.validate_claims": True,
        "crt.escalate_research": True,
        "tec.grant_access": False,
        "gov.certify": False,
        "gov.modify_finding": False,
    }

    SYSTEM_PROMPT = """You are Anvesh, the Healthcare Research Agent (SAM-AG-081 · CRT-016) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-081 · Position: CRT-016
- You report to Aarya (AI CCO, SAM-AG-003).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Own healthcare research. Gather validated facts, source citations, and
clinical references for content production. Provide research input to
copywriters. Never fabricate facts or citations. Never provide medical advice.

YOUR REGISTERS
1. Research Brief Register — research requests, topics, deadlines
2. Fact Register — validated facts, sources, citations
3. Source Register — source metadata, credibility, access
4. Claim Validation Register — claims checked, verdict, evidence
5. Research Escalation Register — gaps, blockers, escalations

HARD RULES — NEVER VIOLATE
1. Never fabricate facts, statistics, or citations. Missing = "unavailable".
2. Never provide medical advice or clinical recommendations.
3. Never suppress a research gap or uncertainty.
4. Every fact has a source and citation.
5. Respect tenant isolation.
6. If the local model is down, report it honestly."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "research")
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
                text=f"[MODEL UNAVAILABLE] {e}. Anvesh cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish(BusEnvelope(
                event_type="crt.research",
                source_agent=self.canonical_id,
                target_agent="all",
                payload={"action": action, "task": task},
                tenant_id=kwargs.get("tenant_id", "DEMO-HEALTHCARE-01"),
                severity="info",
            ))
        except Exception:
            pass
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=tokens, status="completed")

    @authority_guard("crt.research_topic")
    def research_topic(
        self,
        client_id: str,
        topic: str,
        brief: dict,
    ) -> dict:
        """Research a healthcare topic."""
        research_id = f"RES-{uuid.uuid4().hex[:6].upper()}"
        return {
            "research_id": research_id,
            "client_id": client_id,
            "topic": topic,
            "brief": brief,
            "status": "in_progress",
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.gather_facts")
    def gather_facts(
        self,
        research_id: str,
        topic: str,
    ) -> dict:
        """Gather validated facts for a topic."""
        return {
            "research_id": research_id,
            "topic": topic,
            "facts": [],
            "status": "gathered",
            "gathered_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.cite_sources")
    def cite_sources(
        self,
        research_id: str,
        facts: list,
        sources: list,
    ) -> dict:
        """Cite sources for gathered facts."""
        citation_id = f"CIT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "citation_id": citation_id,
            "research_id": research_id,
            "facts": facts,
            "sources": sources,
            "status": "cited",
            "cited_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.validate_claims")
    def validate_claim(
        self,
        claim: str,
        evidence: list,
    ) -> dict:
        """Validate a healthcare claim against evidence."""
        verdict = "supported" if len(evidence) > 0 else "unverified"
        return {
            "claim": claim,
            "verdict": verdict,
            "evidence_count": len(evidence),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

    @authority_guard("crt.escalate_research")
    def escalate_research_gap(
        self,
        client_id: str,
        gap_type: str,
        description: str,
    ) -> dict:
        """Escalate a research gap."""
        gap_id = f"GAP-{uuid.uuid4().hex[:6].upper()}"
        return {
            "gap_id": gap_id,
            "client_id": client_id,
            "gap_type": gap_type,
            "description": description,
            "status": "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_research(
        self,
        client_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """List research items (read-only)."""
        return {
            "research": [],
            "count": 0,
            "filter": {"client_id": client_id, "status": status},
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_facts(
        self,
        research_id: str,
    ) -> dict:
        """Get facts for a research item (read-only)."""
        return {
            "research_id": research_id,
            "facts": [],
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
