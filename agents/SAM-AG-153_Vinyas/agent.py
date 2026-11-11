"""Vinyas — Platform Architecture Lead (SAM-AG-153).

Stage 1B service-first agent. Sets system design standards; reviews technical choices.
Service-first: no LLM. Pure code review / standards enforcement.
"""
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Vinyas(BaseAgent):
    """Platform Architecture Lead."""

    canonical_id = "SAM-AG-153"
    name = "Vinyas"
    designation = "Platform Architecture Lead"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.review_design": True,
        "tec.set_standards": True,
        "tec.block_noncompliant": True,
        "tec.grant_access": False,
        "ops.allocate": False,
    }

    STANDARDS = {
        "llm": "Ollama + qwen2.5:7b, serialized calls",
        "db": "PostgreSQL async, append-only audit tables",
        "bus": "Postgres durable log + Redis pub/sub",
        "auth": "Authority guard in code, not prompts",
        "tenant_isolation": "Every query scoped by tenant_id",
    }

    def run(self, task: str, **kwargs) -> AgentResult:
        """Review a technical choice against architecture standards."""
        choice = kwargs.get("choice", task)
        issues = []
        # Simple deterministic checks against standards
        low = choice.lower()
        # Flag any external/cloud LLM/API directly (local-only standard)
        if any(x in low for x in ["openai", "anthropic", "aws", "azure", "cloud", "api key"]):
            if any(x in low for x in ["llm", "model", "api", "summar", "generate", "gpt", "claude"]):
                issues.append("Cloud LLM/API violates local-only standard")
        if "delete" in low and "audit" in low:
            issues.append("Deleting audit data violates append-only standard")
        if "tenant" in low and "scope" not in low and "filter" not in low:
            issues.append("Query may violate tenant isolation — ensure tenant_id scoping")
        verdict = "compliant" if not issues else "non-compliant"
        text = (
            f"Architecture review of: {choice}\n"
            f"Verdict: {verdict}\n"
            f"Standards applied: {list(self.STANDARDS.keys())}\n"
        )
        if issues:
            text += "Issues:\n" + "\n".join(f"  - {i}" for i in issues)
        else:
            text += "No violations detected."
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.review_design")
    def review(self, design_doc: str) -> dict:
        """Review a design doc against standards."""
        result = self.run("review", choice=design_doc)
        return {"verdict": "compliant" if "compliant" in result.text else "non-compliant", "details": result.text}

    @authority_guard("tec.set_standards")
    def get_standards(self) -> dict:
        """Return current architecture standards."""
        return dict(self.STANDARDS)
