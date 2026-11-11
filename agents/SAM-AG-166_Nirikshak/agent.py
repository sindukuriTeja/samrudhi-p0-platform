"""Nirikshak — Observability and Telemetry (SAM-AG-166).

Stage 1B service-first agent. Logs every run: agent, version, time, cost, result.
Service-first: telemetry writer/reader (writes to execution_log).
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Nirikshak(BaseAgent):
    """Observability and Telemetry."""

    canonical_id = "SAM-AG-166"
    name = "Nirikshak"
    designation = "Observability and Telemetry"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.write_telemetry": True,
        "tec.read_telemetry": True,
        "tec.summary": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._log = []

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "summary")
        if action == "write":
            entry = {
                "agent_id": kwargs.get("agent_id", "unknown"),
                "task": task,
                "tokens": kwargs.get("tokens", 0),
                "at": datetime.now(timezone.utc).isoformat(),
            }
            self._log.append(entry)
            text = f"Telemetry written for {entry['agent_id']}"
        elif action == "summary":
            total = len(self._log)
            total_tokens = sum(e.get("tokens", 0) for e in self._log)
            text = f"Telemetry summary: {total} runs, {total_tokens} total tokens"
        elif action == "read":
            agent_id = kwargs.get("agent_id", "")
            entries = [e for e in self._log if e["agent_id"] == agent_id] if agent_id else self._log
            text = f"Recent telemetry ({len(entries)} entries):\n" + "\n".join(str(e) for e in entries[-5:])
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.write_telemetry")
    def write(self, agent_id: str, task: str, tokens: int = 0) -> dict:
        entry = {"agent_id": agent_id, "task": task, "tokens": tokens, "at": datetime.now(timezone.utc).isoformat()}
        self._log.append(entry)
        return entry

    @authority_guard("tec.summary")
    def summary(self) -> dict:
        total = len(self._log)
        total_tokens = sum(e.get("tokens", 0) for e in self._log)
        return {"total_runs": total, "total_tokens": total_tokens}
