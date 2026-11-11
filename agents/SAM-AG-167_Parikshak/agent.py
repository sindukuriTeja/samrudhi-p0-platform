"""Parikshak — Testing and Evaluation Engineering (SAM-AG-167).

Stage 1B service-first agent. Test sets and regression tests for agents.
Service-first: test runner / registry.
"""
from datetime import datetime, timezone
from agents.base import BaseAgent, AgentResult, register_agent
from backend.core.authority import authority_guard


@register_agent
class Parikshak(BaseAgent):
    """Testing and Evaluation Engineering."""

    canonical_id = "SAM-AG-167"
    name = "Parikshak"
    designation = "Testing and Evaluation Engineering"
    agent_type = "service-first"

    AUTHORITY = {
        "tec.run_tests": True,
        "tec.register_test": True,
        "tec.list_tests": True,
        "ops.allocate": False,
    }

    def __init__(self, canonical_id=None):
        super().__init__(canonical_id)
        self._tests = {}
        self._results = []

    def run(self, task: str, **kwargs) -> AgentResult:
        action = kwargs.get("action", "list")
        if action == "list":
            text = "Registered tests:\n" + "\n".join(f"  - {k}: {v}" for k, v in self._tests.items()) or "  (none)"
        elif action == "run":
            agent_id = kwargs.get("agent_id", "")
            test_id = kwargs.get("test_id", "")
            passed = kwargs.get("passed", True)
            self._results.append({
                "agent_id": agent_id, "test_id": test_id, "passed": passed,
                "at": datetime.now(timezone.utc).isoformat(),
            })
            text = f"Test {test_id} for {agent_id}: {'PASSED' if passed else 'FAILED'}"
        elif action == "results":
            agent_id = kwargs.get("agent_id", "")
            res = [r for r in self._results if r["agent_id"] == agent_id] if agent_id else self._results
            passed = sum(1 for r in res if r["passed"])
            text = f"Test results for {agent_id or 'all'}: {passed}/{len(res)} passed"
        else:
            text = f"Unknown action: {action}"
        return AgentResult(text=text, agent_id=self.canonical_id, tokens_used=0, status="completed")

    @authority_guard("tec.run_tests")
    def record_result(self, agent_id: str, test_id: str, passed: bool) -> dict:
        rec = {"agent_id": agent_id, "test_id": test_id, "passed": passed, "at": datetime.now(timezone.utc).isoformat()}
        self._results.append(rec)
        return rec

    @authority_guard("tec.list_tests")
    def list_results(self, agent_id: str = "") -> list:
        if agent_id:
            return [r for r in self._results if r["agent_id"] == agent_id]
        return list(self._results)
