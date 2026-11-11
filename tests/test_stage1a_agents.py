"""Tests for Stage 1A core agents.

These tests verify agent registration, authority enforcement, and graceful
handling when Ollama is unavailable (agents must report honestly, not crash).
"""
import pytest
from agents.base import load_all, get_agent_module, get_agent_class


@pytest.fixture(autouse=True)
def _load_agents():
    load_all()


def test_all_stage1a_agents_registered():
    """All four Stage 1A agents are registered."""
    expected = {"SAM-AG-001", "SAM-AG-007", "SAM-AG-010", "SAM-AG-158"}
    assert expected.issubset(set(load_all()))


def test_arjun_identity():
    a = get_agent_module("SAM-AG-001")
    assert a.name == "Arjun"
    assert a.designation == "AI Chief Executive Officer"
    assert a.agent_type == "thinking"


def test_sutra_identity():
    a = get_agent_module("SAM-AG-007")
    assert a.name == "Sutra"
    assert a.agent_type == "thinking"


def test_satya_identity():
    a = get_agent_module("SAM-AG-010")
    assert a.name == "Satya"
    assert a.agent_type == "thinking"


def test_niyantrak_identity():
    a = get_agent_module("SAM-AG-158")
    assert a.name == "Niyantrak"
    assert a.agent_type == "thinking"


def test_arjun_authority_enforced():
    """Arjun cannot approve capital or override assurance."""
    from backend.core.authority import AuthorityError, check_authority
    # ops.approve_pricing is False in Arjun's matrix
    with pytest.raises(AuthorityError):
        check_authority("SAM-AG-001", "ops.approve_pricing")
    # gov.override_assurance is False
    with pytest.raises(AuthorityError):
        check_authority("SAM-AG-001", "gov.override_assurance")


def test_satya_finding_immutable_flag():
    """Satya raises findings marked immutable."""
    from backend.core.authority import AuthorityError
    s = get_agent_module("SAM-AG-010")
    # gov.modify_finding is False
    from backend.core.authority import check_authority
    with pytest.raises(AuthorityError):
        check_authority("SAM-AG-010", "gov.modify_finding")


def test_agent_run_reports_model_unavailable_gracefully():
    """When Ollama is down, agents return a failed result instead of crashing."""
    a = get_agent_module("SAM-AG-001")
    result = a.run("produce a daily brief")
    # Without Ollama running, this should be a graceful failure
    assert result.agent_id == "SAM-AG-001"
    assert result.status in ("completed", "failed")
    assert "[MODEL UNAVAILABLE]" in result.text or result.status == "completed"


def test_satya_raise_finding_tool():
    """Satya's raise_finding tool returns an immutable finding record."""
    s = get_agent_module("SAM-AG-010")
    finding = s.raise_finding(
        agent_id="SAM-AG-001",
        severity="S2",
        description="Test finding",
        evidence_refs=["exec-123"],
    )
    assert finding["severity"] == "S2"
    assert finding["immutable"] is True
    assert finding["raised_by"] == "SAM-AG-010"
    assert finding["status"] == "open"


def test_arjun_recommend_initiative_tool():
    """Arjun's recommend_initiative returns a pending-approval record."""
    a = get_agent_module("SAM-AG-001")
    rec = a.recommend_initiative("Launch campaign X", "OBJ-2026-01")
    assert rec["status"] == "pending_approval"
    assert rec["objective_ref"] == "OBJ-2026-01"
