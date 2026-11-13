"""Tests for the Stage 1C assurance team (Satya's team), as defined in the PDF canonical
registry (Document 01C, department 11 — Independent Assurance, GOV-002 … GOV-018).

Service-first agents run in code only; role agents may use the model to judge but never
produce the work they assess. Rules that the documents require in code are tested here.
"""
import pytest

from agents.base import load_all, get_agent_module
from backend.core.authority import AuthorityError, check_authority


@pytest.fixture(autouse=True)
def _load_agents():
    load_all()


STAGE1C = {
    "SAM-AG-176": ("Pramana", "service-first"),
    "SAM-AG-177": ("Nishtha", "service-first"),
    "SAM-AG-178": ("Maryada", "service-first"),
    "SAM-AG-181": ("Yogyata", "role"),
    "SAM-AG-182": ("Pramanik", "role"),
    "SAM-AG-183": ("Gunvatta", "role"),
    "SAM-AG-184": ("Nishpaksh", "role"),
    "SAM-AG-185": ("Seema", "service-first"),
    "SAM-AG-186": ("Swasthya", "role"),
    "SAM-AG-187": ("Gopniya", "service-first"),
    "SAM-AG-189": ("Sakshi", "service-first"),
    "SAM-AG-192": ("Sankat", "service-first"),
}


def test_all_stage1c_agents_registered_with_pdf_names():
    loaded = set(load_all())
    assert set(STAGE1C).issubset(loaded)
    for cid, (name, _) in STAGE1C.items():
        assert get_agent_module(cid).name == name


def test_stage1c_agent_types():
    for cid, (_, kind) in STAGE1C.items():
        assert get_agent_module(cid).agent_type == kind, cid


def test_stage1c_report_to_satya_and_cannot_certify():
    for cid in STAGE1C:
        a = get_agent_module(cid)
        assert "SAM-AG-010" in a.SYSTEM_PROMPT
        with pytest.raises(AuthorityError):
            check_authority(cid, "gov.certify")
        with pytest.raises(AuthorityError):
            check_authority(cid, "gov.modify_finding")


def test_service_first_agents_never_call_the_model(monkeypatch):
    import sys
    called = []

    async def boom(*a, **k):
        called.append(1)
        raise AssertionError("service-first agents must not call the model")
    for name, mod in list(sys.modules.items()):
        if name.startswith("agents.loaded_") and hasattr(mod, "generate"):
            monkeypatch.setattr(mod, "generate", boom)
    for cid, (_, kind) in STAGE1C.items():
        if kind == "service-first":
            r = get_agent_module(cid).run("status check")
            assert r.tokens_used == 0 and r.status == "completed"
    assert not called


def test_satya_independence():
    s = get_agent_module("SAM-AG-010")
    assert s.AUTHORITY.get("gov.escalate_critical") is True
    assert s.AUTHORITY.get("gov.modify_finding") is False


def test_swasthya_blocks_high_risk_claims():
    sw = get_agent_module("SAM-AG-186")
    bad = sw.screen_claims("Our herbal tea is a guaranteed cure with no side effects.")
    assert bad["status"] == "block" and "guaranteed cure" in bad["flags"]
    ok = sw.screen_claims("Healthy food and daily walks support good sugar control. Ask your doctor.")
    assert ok["status"] == "pass"
    client_rule = sw.screen_claims("Feel better naturally", extra_forbidden=["naturally"])
    assert client_rule["status"] == "block"


def test_gopniya_finds_personal_and_other_client_data():
    g = get_agent_module("SAM-AG-187")
    r = g.check_privacy("Call 9876543210 or write to a@b.com. Also see CityCare's offer.", ["CityCare"])
    assert r["status"] == "block"
    assert {"PHONE_NUMBER", "EMAIL_ADDRESS", "OTHER_CLIENT:CityCare"} <= set(r["findings"])
    assert g.check_privacy("Free sugar check on Saturday.")["status"] == "pass"


def test_gunvatta_cannot_score_its_own_output():
    gv = get_agent_module("SAM-AG-183")
    with pytest.raises(ValueError):
        gv.evaluate_output("text", producer_agent="SAM-AG-183")
    r = gv.evaluate_output("Visit the clinic. Ask your doctor.", producer_agent="SAM-AG-082",
                           required_elements=["Ask your doctor", "call to action"])
    assert r["missing_elements"] == ["call to action"] and r["passed"] is False


def test_nishpaksh_scores_in_code():
    r = get_agent_module("SAM-AG-184").score_agent("SAM-AG-082", {"quality": 0.9, "speed": 0.6},
                                                   {"quality": 2, "speed": 1})
    assert r["score"] == pytest.approx(0.8)
    assert get_agent_module("SAM-AG-184").score_agent("SAM-AG-082", {})["status"] == "unavailable"


def test_yogyata_and_pramanik_recommend_only():
    t = get_agent_module("SAM-AG-181").run_competency_test(
        "SAM-AG-082", [{"expected": 1, "actual": 1}, {"expected": 2, "actual": 3}])
    assert t["pass_rate"] == 0.5
    rec = get_agent_module("SAM-AG-182").recommend_certification("SAM-AG-082", t["pass_rate"])
    assert rec["status"] == "not_recommended"
    rec2 = get_agent_module("SAM-AG-182").recommend_certification("SAM-AG-082", 0.95)
    assert rec2["status"] == "recommended_pending_human"


def test_seema_audits_permissions_against_the_matrix():
    se = get_agent_module("SAM-AG-185")
    assert se.audit_permission_use("SAM-AG-082", "crt.write_copy")["allowed"] is True
    assert se.audit_permission_use("SAM-AG-082", "gov.certify")["allowed"] is False


def test_sakshi_flags_missing_evidence():
    sk = get_agent_module("SAM-AG-189")
    r = sk.check_evidence_trail({"execution_id": "exec-1", "agent_id": "SAM-AG-082", "status": "completed"})
    assert r["status"] == "incomplete_evidence" and set(r["missing_fields"]) == {"started_at", "ended_at"}


def test_sankat_only_raises_critical_alerts():
    sn = get_agent_module("SAM-AG-192")
    with pytest.raises(ValueError):
        sn.raise_critical_alert("test", "minor thing", severity="info")
    r = sn.raise_critical_alert("test", "client data leak", severity="S1")
    assert r["routed_to"] == "HUMAN-BOARD" and r["status"] == "raised"


def test_stage1c_total_count():
    loaded = set(load_all())
    assert len([a for a in loaded if a in STAGE1C]) == 12
