"""Tests for Stage 1B service-first agents.

These agents are deterministic services (no LLM). Tests verify registration,
authority enforcement, and core service behavior.
"""
import pytest
from agents.base import load_all, get_agent_module


@pytest.fixture(autouse=True)
def _load_agents():
    load_all()


STAGE1B_IDS = [
    "SAM-AG-153", "SAM-AG-154", "SAM-AG-155", "SAM-AG-156", "SAM-AG-157",
    "SAM-AG-159", "SAM-AG-160", "SAM-AG-161", "SAM-AG-162", "SAM-AG-163",
    "SAM-AG-166", "SAM-AG-167", "SAM-AG-168", "SAM-AG-170",
]


def test_all_stage1b_agents_registered():
    """All 14 Stage 1B agents are registered."""
    loaded = set(load_all())
    assert set(STAGE1B_IDS).issubset(loaded)


def test_stage1b_agents_are_service_first():
    """All Stage 1B agents are service-first type."""
    for cid in STAGE1B_IDS:
        a = get_agent_module(cid)
        assert a.agent_type == "service-first", f"{cid} is not service-first"


def test_vinyas_architecture_review():
    """Vinyas flags cloud LLM usage as non-compliant."""
    v = get_agent_module("SAM-AG-153")
    result = v.run("review", choice="use OpenAI API for summarization")
    assert "non-compliant" in result.text
    compliant = v.run("review", choice="use local Ollama model")
    assert "compliant" in compliant.text


def test_setubandh_connector_registry():
    """Setubandh returns connector registry."""
    s = get_agent_module("SAM-AG-154")
    connectors = s.list_connectors()
    assert "local_folder" in connectors
    assert connectors["local_folder"]["status"] == "active"


def test_yantra_handoff_resolution():
    """Yantra resolves handoff triggers."""
    y = get_agent_module("SAM-AG-155")
    routes = y.resolve_handoff("platform_change_request")
    assert routes["routes"]  # non-empty


def test_smaran_tenant_isolation():
    """Smaran blocks context fetch without tenant_id."""
    s = get_agent_module("SAM-AG-156")
    blocked = s.scope_context(tenant_id="", agent_id="SAM-AG-001", requested_data="x")
    assert blocked["allowed"] is False
    allowed = s.scope_context(tenant_id="DEMO-HEALTHCARE-01", agent_id="SAM-AG-001", requested_data="x")
    assert allowed["allowed"] is True


def test_suraksha_security_policy():
    """Suraksha flags plaintext credential storage."""
    s = get_agent_module("SAM-AG-157")
    violation = s.check_policy("store credentials in plaintext")
    assert violation["compliant"] is False
    compliant = s.check_policy("log all agent calls")
    assert compliant["compliant"] is True


def test_pehchaan_agent_lookup():
    """Pehchaan finds registered agents."""
    p = get_agent_module("SAM-AG-159")
    found = p.lookup("SAM-AG-001")
    assert found["found"] is True
    assert found["name"] == "Arjun"
    not_found = p.lookup("SAM-AG-999")
    assert not_found["found"] is False


def test_jod_connector_config():
    """Jod configures connectors."""
    j = get_agent_module("SAM-AG-160")
    rec = j.configure("slack", "https://hooks.slack.com/xxx")
    assert rec["status"] == "configured"
    assert "slack" in j.list_connectors()


def test_adhikar_permission_check():
    """Adhikar enforces permissions."""
    a = get_agent_module("SAM-AG-161")
    allowed = a.check("SAM-AG-007", "tec.release")
    assert allowed["allowed"] is True
    denied = a.check("SAM-AG-001", "ops.approve_pricing")
    assert denied["allowed"] is False


def test_sandarbhika_context_retrieval():
    """Sandarbhika blocks retrieval without tenant_id."""
    s = get_agent_module("SAM-AG-163")
    blocked = s.retrieve(tenant_id="", scope="general")
    assert blocked["allowed"] is False
    allowed = s.retrieve(tenant_id="DEMO-HEALTHCARE-01", scope="general")
    assert allowed["allowed"] is True


def test_pravahika_workflow_runtime():
    """Pravahika runs workflow state machine."""
    p = get_agent_module("SAM-AG-162")
    rec = p.start_workflow("wf-001", ["step1", "step2", "step3"])
    assert rec["status"] == "running"
    state = p.get_state("wf-001")
    assert state["current"] == 0


def test_nirikshak_telemetry():
    """Nirikshak writes and summarizes telemetry."""
    n = get_agent_module("SAM-AG-166")
    n.write("SAM-AG-001", "daily brief", tokens=1200)
    n.write("SAM-AG-007", "health check", tokens=300)
    summary = n.summary()
    assert summary["total_runs"] == 2
    assert summary["total_tokens"] == 1500


def test_parikshak_test_results():
    """Parikshak records test results."""
    p = get_agent_module("SAM-AG-167")
    p.record_result("SAM-AG-001", "test_auth", passed=True)
    p.record_result("SAM-AG-001", "test_bus", passed=False)
    results = p.list_results("SAM-AG-001")
    assert len(results) == 2
    passed = sum(1 for r in results if r["passed"])
    assert passed == 1


def test_sanskaran_versioning():
    """Sanskaran tags versions and supports rollback."""
    s = get_agent_module("SAM-AG-168")
    s.tag("SAM-AG-001", "1.0.0")
    s.tag("SAM-AG-001", "1.1.0")
    versions = s.list_versions("SAM-AG-001")
    assert len(versions) == 2
    rollback = s.run("", action="rollback", agent_id="SAM-AG-001")
    assert "Rolled back" in rollback.text


def test_chaukidar_security_monitoring():
    """Chaukidar flags S1/S2 threats."""
    c = get_agent_module("SAM-AG-170")
    c.ingest_event("unauthorized access attempt")  # S1
    c.ingest_event("routine check")  # info
    report = c.report()
    assert report["threats_flagged"] == 1
    assert report["total_events"] == 2


def test_stage1b_authority_enforced():
    """Stage 1B agents deny operations outside their authority."""
    from backend.core.authority import AuthorityError, check_authority
    # Vinyas cannot grant access
    with pytest.raises(AuthorityError):
        check_authority("SAM-AG-153", "tec.grant_access")
    # Adhikar cannot grant access alone
    with pytest.raises(AuthorityError):
        check_authority("SAM-AG-161", "tec.grant_access")
