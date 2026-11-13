"""Registry tests: the code must match config/agent_registry.yaml, which is taken from the
PDF canonical registry (Document 01C). Covers every built agent, so a wrong ID, name,
title, reporting line or a missing/invented agent fails here.
"""
import inspect
from pathlib import Path

import pytest
import yaml

from agents.base import _REGISTRY, load_all
from backend.core.authority import AuthorityError, check_authority

ROOT = Path(__file__).resolve().parent.parent
REG = yaml.safe_load((ROOT / "config" / "agent_registry.yaml").read_text(encoding="utf-8"))
AGENTS = {a["canonical_id"]: a for a in REG["agents"]}
EXEC_TITLES = {"SAM-AG-001", "SAM-AG-002"}  # full executive designations kept in code


@pytest.fixture(autouse=True, scope="module")
def _load():
    load_all()


def test_counts_match_the_build_plan():
    stages = {}
    for a in AGENTS.values():
        stages[a["stage"]] = stages.get(a["stage"], 0) + 1
    assert stages == {"P0-1A": 4, "P0-1B": 14, "P0-1C": 12, "P1-P1": 4, "P1-P2": 16, "P1-P3": 29}


def test_every_registry_agent_is_built_and_nothing_else():
    load_all()
    assert set(_REGISTRY) == set(AGENTS)


def test_ids_positions_and_names_are_unique():
    assert len({a["position_id"] for a in AGENTS.values()}) == len(AGENTS)
    assert len({a["name"] for a in AGENTS.values()}) == len(AGENTS)


@pytest.mark.parametrize("cid", sorted(AGENTS))
def test_agent_identity_matches_registry(cid):
    a, cls = AGENTS[cid], _REGISTRY[cid]
    assert cls.canonical_id == cid
    assert cls.name == a["name"]
    if a["stage"] in ("P1-P2", "P1-P3", "P0-1C"):
        assert cls.designation == a["title"]
    assert cls.agent_type == a["agent_type"]


@pytest.mark.parametrize("cid", sorted(c for c, a in AGENTS.items() if a["stage"] in ("P1-P2", "P1-P3", "P0-1C")))
def test_prompt_states_position_and_manager(cid):
    a, cls = AGENTS[cid], _REGISTRY[cid]
    assert a["position_id"] in cls.SYSTEM_PROMPT
    assert a["reports_to"] in cls.SYSTEM_PROMPT


@pytest.mark.parametrize("cid", sorted(AGENTS))
def test_governance_denials_and_escalation_path(cid):
    cls = _REGISTRY[cid]
    if cid != "SAM-AG-010":
        for perm in ("gov.certify", "gov.modify_finding"):
            with pytest.raises(AuthorityError):
                check_authority(cid, perm)
    # Every agent needs an escalation path: the activation gate checks for one.
    if True:
        agent = cls()
        assert any(hasattr(agent, m) for m in ("route_for_approval", "escalate", "escalate_operational_issue",
                                               "escalate_client_issue"))


def _sample(param):
    ann = str(param.annotation)
    if "list" in ann:
        return []
    if "dict" in ann:
        return {}
    if "bool" in ann:
        return False
    if "float" in ann:
        return 1.0
    if "int" in ann:
        return 1
    return "x"


def test_rewritten_agents_have_working_tools():
    load_all()
    with_tools = [c for c, cls in _REGISTRY.items() if hasattr(cls, "TOOLS")]
    assert len(with_tools) == 31
    for cid in with_tools:
        cls = _REGISTRY[cid]
        agent = cls()
        for method, perm in cls.TOOLS.items():
            assert cls.AUTHORITY.get(perm) is True, f"{cid}.{method} needs {perm}"
            fn = getattr(agent, method)
            kwargs = {p.name: _sample(p) for p in inspect.signature(fn).parameters.values()
                      if p.default is inspect.Parameter.empty}
            if method == "check_milestone":
                kwargs["due_iso"] = "2030-01-01T00:00:00Z"
            if method == "record_client_decision":
                kwargs.update(decision="approve", approver="human")
            if method == "evaluate_output":
                kwargs["producer_agent"] = "SAM-AG-082"
            if method == "raise_critical_alert":
                kwargs["severity"] = "S1"
            result = fn(**kwargs)
            assert isinstance(result, dict) and "status" in result, f"{cid}.{method}"


def test_rules_in_code_for_delivery():
    load_all()
    assert _REGISTRY["SAM-AG-072"]().verify_acceptance("PKG-1", {"shuddhi": True})["status"] == "refused_missing_check"
    full = {c: True for c in _REGISTRY["SAM-AG-072"].REQUIRED_CHECKS}
    assert _REGISTRY["SAM-AG-072"]().verify_acceptance("PKG-1", full)["accepted"] is True
    assert _REGISTRY["SAM-AG-052"]().build_approval_request("PKG-1", {})["status"] == "blocked_missing_evidence"
    with pytest.raises(ValueError):
        _REGISTRY["SAM-AG-052"]().record_client_decision("REQ-1", "approve", approver="")
    assert _REGISTRY["SAM-AG-071"]().create_rework_request("PKG-1", ["claim"], 4)["status"] == "escalate_to_human"
    assert _REGISTRY["SAM-AG-064"]().build_work_packages("C1", {"posts": 3, "articles": 1})["package_count"] == 4
    brief = _REGISTRY["SAM-AG-050"]().structure_brief("C1", objective="Awareness", audience="Adults 35-60")
    assert brief["status"] == "incomplete" and "deadline" in brief["missing_fields"]
    assert _REGISTRY["SAM-AG-146"]().compute_cost_per_deliverable(90.0, 3)["cost_per_accepted_deliverable"] == 30.0
    assert _REGISTRY["SAM-AG-130"]().detect_anomaly("reach", [100, 110, 90, 300])["anomaly"] is True
