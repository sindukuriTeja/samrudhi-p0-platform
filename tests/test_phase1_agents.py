"""Tests for Phase 1 P1 pilot leadership agents (Daksh, Aarya, Mitra, Medha).

These are executive thinking agents (LLM-based) with deterministic tool methods.
Tests verify registration, authority enforcement, and tool behavior.
"""
import pytest
from agents.base import load_all, get_agent_module


@pytest.fixture(autouse=True)
def _load_agents():
    load_all()


PHASE1_IDS = [
    "SAM-AG-002", "SAM-AG-003", "SAM-AG-004", "SAM-AG-009",
]


def test_all_phase1_agents_registered():
    """All 4 Phase 1 agents are registered."""
    loaded = set(load_all())
    assert set(PHASE1_IDS).issubset(loaded)


def test_phase1_agents_are_thinking():
    """All Phase 1 agents are thinking type."""
    for cid in PHASE1_IDS:
        a = get_agent_module(cid)
        assert a.agent_type == "thinking", f"{cid} is not thinking"


def test_phase1_agents_have_authority():
    """All Phase 1 agents have AUTHORITY dict."""
    for cid in PHASE1_IDS:
        a = get_agent_module(cid)
        assert hasattr(a, "AUTHORITY"), f"{cid} missing AUTHORITY"
        assert isinstance(a.AUTHORITY, dict), f"{cid} AUTHORITY not a dict"


def test_phase1_agents_reports_to_arjun():
    """All Phase 1 agents report to Arjun (CEO)."""
    for cid in PHASE1_IDS:
        a = get_agent_module(cid)
        assert "Arjun" in a.SYSTEM_PROMPT, f"{cid} does not mention Arjun"


# -----------------------------------------------------------------------------
# Daksh (SAM-AG-002) — AI COO
# -----------------------------------------------------------------------------

def test_daksh_create_workflow():
    """Daksh creates a delivery workflow."""
    d = get_agent_module("SAM-AG-002")
    result = d.create_workflow("CLIENT-001", "SCOPE-001", {"phase1": "2026-12-01"})
    assert result["workflow_id"].startswith("WF-")
    assert result["client_id"] == "CLIENT-001"
    assert result["status"] == "created"


def test_daksh_transition_workflow():
    """Daksh transitions workflow through state machine."""
    d = get_agent_module("SAM-AG-002")
    result = d.transition_workflow("WF-001", "planning")
    assert result["new_status"] == "planning"
    bad = d.transition_workflow("WF-001", "nonexistent")
    assert "error" in bad


def test_daksh_allocate_capacity_ok():
    """Daksh allocates when capacity is available."""
    d = get_agent_module("SAM-AG-002")
    result = d.allocate_work_package("WF-001", "Social posts", "content", "SAM-AG-153", capacity_ok=True)
    assert result["status"] == "allocated"
    assert result["assigned_agent"] == "SAM-AG-153"


def test_daksh_allocate_capacity_fail():
    """Daksh refuses allocation when capacity is exhausted."""
    d = get_agent_module("SAM-AG-002")
    result = d.allocate_work_package("WF-001", "Social posts", "content", "SAM-AG-153", capacity_ok=False)
    assert result["error"] == "capacity_violation"


def test_daksh_check_capacity():
    """Daksh checks agent capacity."""
    d = get_agent_module("SAM-AG-002")
    result = d.check_capacity("SAM-AG-153", 10)
    assert "can_accept" in result
    assert "utilisation" in result


def test_daksh_escalate_blocker():
    """Daksh escalates a delivery blocker."""
    d = get_agent_module("SAM-AG-002")
    result = d.escalate_blocker("WF-001", "S1", "Creative blocked", ["SAM-AG-003"])
    assert result["status"] == "escalated"
    assert result["severity"] == "S1"


def test_daksh_get_workflow_state():
    """Daksh returns workflow state machine."""
    d = get_agent_module("SAM-AG-002")
    result = d.get_workflow_state("WF-001")
    assert "state_machine" in result
    assert "created" in result["state_machine"]


# -----------------------------------------------------------------------------
# Aarya (SAM-AG-003) — AI CCO
# -----------------------------------------------------------------------------

def test_aarya_create_strategy():
    """Aarya creates a content strategy."""
    a = get_agent_module("SAM-AG-003")
    result = a.create_content_strategy(
        "CLIENT-001",
        {"pillars": ["education"]},
        {"themes": ["preventive"]},
        {"messaging": ["care"]},
        {"audience": ["patients"]},
    )
    assert result["strategy_id"].startswith("STRAT-")
    assert result["client_id"] == "CLIENT-001"


def test_aarya_build_calendar():
    """Aarya builds an editorial calendar."""
    a = get_agent_module("SAM-AG-003")
    result = a.build_content_calendar("CLIENT-001", "2026-01-01", "2026-01-31", [{"platform": "instagram"}])
    assert result["calendar_id"].startswith("CAL-")
    assert len(result["items"]) == 1


def test_aarya_assign_package():
    """Aarya assigns a content package to a specialist."""
    a = get_agent_module("SAM-AG-003")
    result = a.assign_content_package("CAL-001", "Health tips post", "post", "Lekha")
    assert result["status"] == "allocated"
    assert result["specialist"] == "Lekha"


def test_aarya_brand_check_pass():
    """Aarya brand check passes for compliant content."""
    a = get_agent_module("SAM-AG-003")
    result = a.brand_compliance_check("CPKG-001", "Good health content", {"version": "1.0"})
    assert result["compliant"] is True


def test_aarya_brand_check_fail():
    """Aarya brand check fails for empty content."""
    a = get_agent_module("SAM-AG-003")
    result = a.brand_compliance_check("CPKG-001", "  ", {"version": "1.0"})
    assert result["compliant"] is False
    assert "EMPTY_CONTENT" in result["issues"]


def test_aarya_qa_review():
    """Aarya runs a QA review."""
    a = get_agent_module("SAM-AG-003")
    passed = a.qa_review("CPKG-001", "SAM-AG-003", {"critical": []})
    assert passed["passed"] is True
    failed = a.qa_review("CPKG-001", "SAM-AG-003", {"critical": ["unsupported claim"]})
    assert failed["passed"] is False


def test_aarya_reject_content():
    """Aarya rejects non-compliant content."""
    a = get_agent_module("SAM-AG-003")
    result = a.reject_content("CPKG-001", "Unsupported medical claim", ["remove claim"])
    assert result["rejected"] is True
    assert result["status"] == "blocked"


# -----------------------------------------------------------------------------
# Mitra (SAM-AG-004) — AI CXO
# -----------------------------------------------------------------------------

def test_mitra_onboard_client():
    """Mitra onboards a new client."""
    m = get_agent_module("SAM-AG-004")
    result = m.onboard_client("CLIENT-001", "CONTRACT-001", {"brief": "healthcare"}, {"workflow": "email"}, {"contact": "x@y.com"})
    assert result["onboarding_id"].startswith("ONB-")
    assert result["client_id"] == "CLIENT-001"


def test_mitra_create_communication():
    """Mitra creates a client communication."""
    m = get_agent_module("SAM-AG-004")
    result = m.create_communication("CLIENT-001", "update", "Weekly progress", "SAM-AG-004")
    assert result["comm_id"].startswith("COMM-")
    assert result["type"] == "update"


def test_mitra_route_approval():
    """Mitra routes an item for approval."""
    m = get_agent_module("SAM-AG-004")
    result = m.route_for_approval("CLIENT-001", "CONTENT-001", "client-approver")
    assert result["status"] == "pending"
    assert result["approver"] == "client-approver"


def test_mitra_record_feedback():
    """Mitra records client feedback."""
    m = get_agent_module("SAM-AG-004")
    result = m.record_feedback("CLIENT-001", "email", "suggestion", "Aarya")
    assert result["feedback_id"].startswith("FB-")
    assert result["status"] == "open"


def test_mitra_update_account_health():
    """Mitra updates account health."""
    m = get_agent_module("SAM-AG-004")
    result = m.update_account_health("CLIENT-001", 4.5, {"engagement": "high"}, "ready", {})
    assert result["satisfaction"] == 4.5
    assert result["renewal_readiness"] == "ready"


def test_mitra_escalate_client_issue():
    """Mitra escalates a client issue."""
    m = get_agent_module("SAM-AG-004")
    result = m.escalate_client_issue("CLIENT-001", "S1", "Client unhappy", ["SLA"])
    assert result["status"] == "escalated"
    assert result["severity"] == "S1"


# -----------------------------------------------------------------------------
# Medha (SAM-AG-009) — AI Head of Intelligence
# -----------------------------------------------------------------------------

def test_medha_define_kpi():
    """Medha defines a KPI."""
    m = get_agent_module("SAM-AG-009")
    result = m.define_kpi("KPI-001", "On-time rate", "delivered/on_total", {"source": "workflow"})
    assert result["kpi_id"] == "KPI-001"
    assert result["formula"] == "delivered/on_total"


def test_medha_produce_report():
    """Medha produces a validated report."""
    m = get_agent_module("SAM-AG-009")
    result = m.produce_report("client", "CLIENT-001", "report-ref", {"sources": ["CRM"]})
    assert result["report_id"].startswith("RPT-")
    assert result["status"] == "validated"


def test_medha_run_forecast():
    """Medha runs a forecast."""
    m = get_agent_module("SAM-AG-009")
    result = m.run_forecast("revenue", 150000, {"lower": 140000, "upper": 160000}, {"method": "trend"})
    assert result["forecast_id"].startswith("FCST-")
    assert result["value"] == 150000


def test_medha_detect_anomaly():
    """Medha detects an anomaly."""
    m = get_agent_module("SAM-AG-009")
    result = m.detect_anomaly("metric_spike", "critical", "CTR dropped 40%", {"metric": "ctr"})
    assert result["anomaly_id"].startswith("ANOM-")
    assert result["severity"] == "critical"


def test_medha_validate_data_source():
    """Medha validates a data source."""
    m = get_agent_module("SAM-AG-009")
    result = m.validate_data_source("CRM-001", "CRM", {"completeness": 0.98})
    assert result["connectivity"] == "connected"
    assert result["source_type"] == "CRM"


def test_medha_measure_workforce():
    """Medha measures workforce productivity."""
    m = get_agent_module("SAM-AG-009")
    result = m.measure_workforce("SAM-AG-153", {"posts": 45}, {"capacity": 0.72}, 800.0)
    assert result["agent_id"] == "SAM-AG-153"
    assert result["cost_per_deliverable"] == 800.0


# -----------------------------------------------------------------------------
# Cross-agent tests
# -----------------------------------------------------------------------------

def test_phase1_total_count():
    """Exactly 4 Phase 1 agents registered."""
    loaded = set(load_all())
    phase1 = [a for a in loaded if a in PHASE1_IDS]
    assert len(phase1) == 4


def test_phase1_all_have_13_tools():
    """All Phase 1 agents have at least 10 tools."""
    for cid in PHASE1_IDS:
        a = get_agent_module(cid)
        tools = [m for m in dir(a) if not m.startswith('_') and callable(getattr(a, m)) and m not in ('run', 'describe')]
        assert len(tools) >= 10, f"{cid} has only {len(tools)} tools"
