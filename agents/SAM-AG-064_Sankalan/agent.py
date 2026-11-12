"""Sankalan — Scope-to-Delivery Planning (SAM-AG-064 · OPS-007).

Stage 2 Phase 3 operations, client, analytics and CEO-office agent (P1). Thinking agent: reasons with the local model; tools are authority-guarded and deterministic.
Convert the signed scope and the client brief into delivery requirements and work
packages (for example 20 posts, 4 articles), and flag missing requirements before
production starts. [PDF 01A.05 · OPS-007 Scope-to-Delivery Planning; processes OPS-P02,
OPS-P03]
Reports to Daksh (AI COO, SAM-AG-002).
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
class Sankalan(BaseAgent):
    """Scope-to-Delivery Planning."""

    canonical_id = "SAM-AG-064"
    name = "Sankalan"
    designation = "Scope-to-Delivery Planning"
    agent_type = "thinking"

    AUTHORITY = {
        "ops.analyse_scope": True,
        "ops.build_work_packages": True,
        "ops.map_requirements": True,
        "ops.flag_missing_requirement": True,
        "ops.escalate_scope_gap": True,
        "gov.certify": False,
        "gov.modify_finding": False,
        "tec.grant_access": False,
    }

    # tool method -> permission it requires (checked by the authority guard)
    TOOLS = {
        "analyse_scope": "ops.analyse_scope",
        "build_work_packages": "ops.build_work_packages",
        "map_requirements": "ops.map_requirements",
        "flag_missing_requirement": "ops.flag_missing_requirement",
        "escalate_scope_gap": "ops.escalate_scope_gap",
    }

    SYSTEM_PROMPT = """You are Sankalan, Scope-to-Delivery Planning (SAM-AG-064 · OPS-007) of Samrudhi,
an AI-operated healthcare digital marketing enterprise.

YOUR IDENTITY
- Canonical ID: SAM-AG-064 · Position: OPS-007 · Department: Operations & Delivery Management
- You report to Daksh (AI COO, SAM-AG-002).
- Your technical custodian is Sutra. Your independent evaluator is Satya.

YOUR MISSION
Convert the signed scope and the client brief into delivery requirements and work packages (for
example 20 posts, 4 articles), and flag missing requirements before production starts. [PDF
01A.05 · OPS-007 Scope-to-Delivery Planning; processes OPS-P02, OPS-P03]

YOUR REGISTERS
1. Scope Register — client, signed scope, version
2. Work Package Register — package, type, sequence, status
3. Requirement Gap Register — gap, impact, owner

AUTHORITY MATRIX
ops.analyse_scope · ops.build_work_packages · ops.map_requirements · ops.flag_missing_requirement · ops.escalate_scope_gap
gov.certify=False · gov.modify_finding=False · tec.grant_access=False

HARD RULES — NEVER VIOLATE
1. Never fabricate data. Missing information = "unavailable".
2. Respect tenant isolation: never use one client's data for another.
3. Satya's findings are immutable to you — read-only.
4. Never create packages beyond the signed scope.
5. If the local model is down, report it honestly — do not fake output."""

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        import json
        action = kwargs.get("action", "plan")
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
                text=f"[MODEL UNAVAILABLE] {e}. Sankalan cannot produce output while Ollama is down.",
                agent_id=self.canonical_id,
                tokens_used=0,
                status="failed",
            )
        try:
            bus.publish_sync(BusEnvelope(
                event_type="ops.scope",
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
    # Sankalan's tools (authority-guarded)
    # ------------------------------------------------------------------

    @authority_guard("ops.analyse_scope")
    def analyse_scope(self, client_id: str, signed_scope: str) -> dict:
        """Analyse the signed scope."""
        return {
            "record_id": f"SAN-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "signed_scope": signed_scope,
            "action": "analyse_scope",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.build_work_packages")
    def build_work_packages(self, client_id: str, scope: dict) -> dict:
        """Split scope quantities into work packages."""
        packages = []
        for kind, qty in (scope or {}).items():
            for n in range(1, int(qty) + 1):
                packages.append({"package_id": f"WP-{uuid.uuid4().hex[:6].upper()}",
                                 "type": kind, "sequence": n, "status": "planned"})
        return {
            "client_id": client_id,
            "scope": scope,
            "work_packages": packages,
            "package_count": len(packages),
            "status": "planned" if packages else "empty_scope",
            "built_at": _now(),
        }

    @authority_guard("ops.map_requirements")
    def map_requirements(self, client_id: str, requirements: list) -> dict:
        """Map requirements to packages."""
        return {
            "record_id": f"SAN-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "requirements": requirements,
            "action": "map_requirements",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.flag_missing_requirement")
    def flag_missing_requirement(self, client_id: str, requirement: str) -> dict:
        """Flag a missing requirement."""
        return {
            "record_id": f"SAN-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "requirement": requirement,
            "action": "flag_missing_requirement",
            "status": "recorded",
            "recorded_at": _now(),
        }

    @authority_guard("ops.escalate_scope_gap")
    def escalate_scope_gap(self, client_id: str, gap: str) -> dict:
        """Escalate a scope gap."""
        return {
            "record_id": f"SAN-{uuid.uuid4().hex[:6].upper()}",
            "client_id": client_id,
            "gap": gap,
            "action": "escalate_scope_gap",
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
