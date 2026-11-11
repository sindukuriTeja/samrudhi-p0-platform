"""Tests for Stage 1C assurance agents (Satya's team).

These are thinking agents (LLM-based) with deterministic tool methods.
Tests verify registration, authority enforcement, and tool behavior.
"""
import pytest
from agents.base import load_all, get_agent_module


@pytest.fixture(autouse=True)
def _load_agents():
    load_all()


STAGE1C_IDS = [
    "SAM-AG-011", "SAM-AG-012", "SAM-AG-013", "SAM-AG-014", "SAM-AG-015", "SAM-AG-016",
    "SAM-AG-017", "SAM-AG-018", "SAM-AG-019", "SAM-AG-020", "SAM-AG-021", "SAM-AG-022",
]


def test_all_stage1c_agents_registered():
    """All 12 Stage 1C agents are registered."""
    loaded = set(load_all())
    assert set(STAGE1C_IDS).issubset(loaded)


def test_stage1c_agents_are_thinking():
    """All Stage 1C agents are thinking type."""
    for cid in STAGE1C_IDS:
        a = get_agent_module(cid)
        assert a.agent_type == "thinking", f"{cid} is not thinking"


def test_stage1c_agents_have_authority():
    """All Stage 1C agents have AUTHORITY dict."""
    for cid in STAGE1C_IDS:
        a = get_agent_module(cid)
        assert hasattr(a, "AUTHORITY"), f"{cid} missing AUTHORITY"
        assert isinstance(a.AUTHORITY, dict), f"{cid} AUTHORITY not a dict"


def test_satya_independence():
    """Satya reports critical risks to Board, not Arjun."""
    s = get_agent_module("SAM-AG-010")
    assert s.AUTHORITY.get("gov.escalate_critical") is True
    assert s.AUTHORITY.get("gov.modify_finding") is False


def test_prakash_compliance_check_patient_data():
    """Prakash blocks patient data access without consent."""
    p = get_agent_module("SAM-AG-011")
    result = p.check_action("read", "agent-x", "patient_data", "TENANT-1", consent_verified=False)
    assert result["compliant"] is False
    assert "PATIENT_CONSENT_MISSING" in result["violations"]


def test_prakash_compliance_check_with_consent():
    """Prakash allows patient data access with consent."""
    p = get_agent_module("SAM-AG-011")
    result = p.check_action("read", "agent-x", "patient_data", "TENANT-1", consent_verified=True)
    assert result["compliant"] is True
    assert result["violations"] == []


def test_prakash_cross_tenant_blocked():
    """Prakash always blocks cross-tenant data flow."""
    p = get_agent_module("SAM-AG-011")
    result = p.check_action("export", "agent-x", "cross_tenant", "TENANT-1")
    assert result["compliant"] is False
    assert "CROSS_TENANT_BLOCKED" in result["violations"]


def test_rajat_risk_scoring():
    """Rajat scores risk as likelihood × impact."""
    r = get_agent_module("SAM-AG-012")
    result = r.score_risk("security", "Unusual access pattern", 4, 5, "tenant-1")
    assert result["score"] == 20
    assert result["severity"] == "critical"


def test_rajat_risk_severity_levels():
    """Rajat assigns correct severity levels."""
    r = get_agent_module("SAM-AG-012")
    low = r.score_risk("perf", "Minor latency", 1, 2, "tenant-1")
    assert low["severity"] == "low"
    high = r.score_risk("compliance", "Policy gap", 3, 4, "tenant-1")
    assert high["severity"] == "high"


def test_niti_policy_update():
    """Niti updates policy with version bump."""
    n = get_agent_module("SAM-AG-013")
    result = n.update_policy("POL-001", "1.1", "Updated HIPAA compliance rules", "all")
    assert result["policy_id"] == "POL-001"
    assert result["version"] == "1.1"
    assert result["immutable"] is True


def test_satark_security_review():
    """Satark reviews security and flags anomalies."""
    s = get_agent_module("SAM-AG-014")
    result = s.review_security("agent-x", [{"action": "read", "data": "patient"}])
    assert "review_id" in result
    assert "risk_level" in result


def test_sachit_evidence_storage():
    """Sachit stores immutable evidence with hash."""
    sc = get_agent_module("SAM-AG-015")
    result = sc.store_evidence("FIN-001", "log", "agent accessed patient data")
    assert "evidence_id" in result
    assert result["immutable"] is True
    assert "hash" in result


def test_pramaan_certification():
    """Pramaan certifies agent at a level."""
    p = get_agent_module("SAM-AG-016")
    result = p.certify("SAM-AG-153", "C3", ["EVID-001", "EVID-002"])
    assert result["agent_id"] == "SAM-AG-153"
    assert result["level"] == "C3"
    assert len(result["evidence_refs"]) == 2


def test_aarogya_quality_check_pass():
    """Aarogya passes quality check when no issues."""
    a = get_agent_module("SAM-AG-017")
    result = a.run_quality_check("SAM-AG-153", "output text", ["completeness", "accuracy"])
    assert "check_id" in result
    assert "score" in result


def test_samay_sla_breach():
    """Samay detects SLA breach."""
    s = get_agent_module("SAM-AG-018")
    result = s.check_sla("SAM-AG-153", "latency_ms", 1000, 1500)
    assert result["breached"] is True


def test_samay_sla_ok():
    """Samay reports SLA compliance."""
    s = get_agent_module("SAM-AG-018")
    result = s.check_sla("SAM-AG-153", "latency_ms", 1000, 500)
    assert result["breached"] is False


def test_sabhyata_audit_query():
    """Sabhyata returns audit entries."""
    s = get_agent_module("SAM-AG-019")
    result = s.query_audit("SAM-AG-153", "2026-01-01", "2026-12-31")
    assert "query_id" in result
    assert "entries" in result
    assert "count" in result


def test_ansh_incident_raise():
    """Ansh raises an incident."""
    a = get_agent_module("SAM-AG-020")
    result = a.raise_incident("S1", "Critical failure", ["SAM-AG-153", "SAM-AG-154"])
    assert "incident_id" in result
    assert result["severity"] == "S1"
    assert result["status"] == "open"


def test_benchmark_performance():
    """Benchmark compares against baseline."""
    b = get_agent_module("SAM-AG-021")
    result = b.benchmark("SAM-AG-153", "accuracy", 0.85)
    assert "benchmark_id" in result
    assert "delta" in result


def test_satark2_anomaly_detection():
    """Satark2 detects anomalies."""
    s = get_agent_module("SAM-AG-022")
    result = s.detect_anomaly("SAM-AG-153", {"cpu": 95, "latency": 2000}, {"cpu": 50, "latency": 500})
    assert "anomaly_id" in result
    assert "severity" in result


def test_stage1c_total_count():
    """Exactly 12 Stage 1C agents registered."""
    loaded = set(load_all())
    stage1c = [a for a in loaded if a in STAGE1C_IDS]
    assert len(stage1c) == 12
