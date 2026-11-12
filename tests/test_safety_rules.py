"""Safety rules enforced in code (config/safety_rules.yaml + backend/core/safety_rules.py)."""
from agents.base import get_agent_module
from backend.core import safety_rules as SR

DISCLAIMER = "Consult your doctor for advice about your health."


def post(caption, headline="World Diabetes Day", cta="Book a sugar check"):
    return {"headline": headline, "caption": caption, "call_to_action": cta}


def kinds(res):
    return [f["rule"] for f in res["findings"]]


# ---------------------------------------------------------------- the rule set
def test_client_rules_add_to_global_rules_and_never_remove_them():
    g = SR.rules_for("UNKNOWN-CLIENT")
    c = SR.rules_for("DEMO-HEALTHCARE-01")
    assert set(g["forbidden_claims"]) <= set(c["forbidden_claims"])
    assert "painless surgery" in c["forbidden_claims"] and "painless surgery" not in g["forbidden_claims"]
    assert c["required_disclaimers"] == [DISCLAIMER] and g["required_disclaimers"] == []
    assert c["known_client"] and not g["known_client"]


def test_other_clients_are_named_but_never_the_client_itself():
    c = SR.rules_for("DEMO-HEALTHCARE-01")
    assert "Sunrise Diabetes Clinic" in c["other_client_names"] and "Sunrise Clinic" in c["other_client_names"]
    assert "Demo Healthcare Hospital" not in c["other_client_names"]
    assert "Demo Healthcare Hospital" in SR.rules_for("DEMO-CLINIC-02")["other_client_names"]


# ---------------------------------------------------------------- the checks
def test_forbidden_claims_and_patterns_are_found_per_post():
    rules = SR.rules_for("DEMO-HEALTHCARE-01")
    res = SR.screen([post(f"Walk daily. {DISCLAIMER}"),
                     post(f"Our diet cures diabetes. {DISCLAIMER}"),
                     post(f"Visit the best hospital in town for painless surgery. {DISCLAIMER}")], rules)
    found = [(f["post"], f["rule"]) for f in res["findings"]]
    assert (2, SR.FORBIDDEN_PATTERN) in found
    assert (3, SR.FORBIDDEN_PATTERN) in found and (3, SR.FORBIDDEN_CLAIM) in found
    assert not any(n == 1 for n, _ in found) and res["passed"] is False


def test_disclaimer_is_required_on_every_post_ignoring_case_and_punctuation():
    rules = SR.rules_for("DEMO-HEALTHCARE-01")
    ok = SR.screen([post("Walk daily. consult your doctor for advice about your health")], rules)
    assert ok["passed"]
    bad = SR.screen([post("Walk daily."), post(f"Eat well. {DISCLAIMER}")], rules)
    assert [(f["post"], f["rule"]) for f in bad["findings"]] == [(1, SR.MISSING_DISCLAIMER)]


def test_statistics_must_come_from_the_research_pack():
    rules = SR.rules_for(None)
    p = [post("1 in 10 adults has diabetes and 40% do not know it.")]
    res = SR.screen(p, rules, evidence="IDF: 1 in 10 adults lives with diabetes.")
    assert [f["detail"] for f in res["findings"]] == ['figure "40%" is not in the research pack']
    assert SR.screen(p, rules, evidence="1 in 10 adults; about 40 % are undiagnosed")["passed"]
    assert SR.screen(p, rules)["passed"]          # no evidence given: the statistics rule is not applied


def test_missing_fields_repeats_and_length():
    rules = {**SR.rules_for(None), "max_caption_chars": 50}
    res = SR.screen([post("Short one."), post("Short one.", headline="unavailable"), post("x" * 51)], rules)
    details = [SR.describe(f) for f in res["findings"]]
    assert "post 2: headline is empty" in details
    assert "post 2: caption repeats an earlier post" in details
    assert "post 3: caption has 51 characters (limit 50)" in details


def test_other_client_name_is_found():
    rules = SR.rules_for("DEMO-HEALTHCARE-01")
    res = SR.screen([post(f"Partnering with Sunrise Clinic. {DISCLAIMER}")], rules, only={SR.OTHER_CLIENT})
    assert kinds(res) == [SR.OTHER_CLIENT]


def test_prompt_text_names_the_disclaimer_but_the_code_still_decides():
    text = SR.prompt_text(SR.rules_for("DEMO-HEALTHCARE-01"))
    assert DISCLAIMER in text and "painless surgery" in text and "research pack" in text


# ---------------------------------------------------------------- the agents use the same rules
def test_swasthya_checks_each_post_for_claims_and_the_disclaimer():
    sw = get_agent_module("SAM-AG-186")
    rules = SR.rules_for("DEMO-HEALTHCARE-01")
    args = dict(extra_forbidden=rules["forbidden_claims"], patterns=rules["forbidden_patterns"],
                required_disclaimers=rules["required_disclaimers"])
    r = sw.screen_claims("", posts=[post(f"Walk daily. {DISCLAIMER}"), post("Zero risk screening.")], **args)
    assert r["status"] == "block" and r["posts_checked"] == 2
    assert "post 2: forbidden claim \"zero risk\"" in r["findings"]
    assert any(x.startswith("post 2: required disclaimer missing") for x in r["findings"])
    ok = sw.screen_claims("Free sugar check", posts=[post(f"Walk daily. {DISCLAIMER}")], **args)
    assert ok["status"] == "pass"
    # text on the artwork is screened for claims too
    art = sw.screen_claims("Guaranteed results!", posts=[post(f"Walk daily. {DISCLAIMER}")], **args)
    assert art["status"] == "block" and "guaranteed outcome" in art["findings"][0]


def test_gunvatta_checks_every_post_is_complete():
    gv = get_agent_module("SAM-AG-183")
    r = gv.evaluate_output("x", producer_agent="SAM-AG-082", posts=[post("A"), post("B", cta="unavailable")],
                           required_fields=["headline", "caption", "call_to_action"], max_chars=2200)
    assert r["passed"] is False and r["defects"] == ["post 2: call_to_action is empty"]
    assert gv.evaluate_output("", producer_agent="SAM-AG-082", posts=[],
                              required_fields=["caption"])["defects"][-1] == "no posts were produced"


def test_prakash_releases_only_human_approved_and_clean_content():
    pk = get_agent_module("SAM-AG-084")
    base = dict(client_id="C1", content_ref="PRJ-1", scheduled_time="2026-11-14", channels=["instagram"])
    clean = {"passed": True, "findings": []}
    human = {"decision": "approve", "decided_by": "vikram"}
    assert pk.schedule_release(**base, approval=human, final_check=clean)["status"] == "scheduled"
    r = pk.schedule_release(**base, approval={"decision": None}, final_check=clean)
    assert r["status"] == "refused" and "no human approval" in r["reasons"][0]
    r = pk.schedule_release(**base, approval={"decision": "approve", "decided_by": "SAM-AG-052"}, final_check=clean)
    assert r["status"] == "refused" and "signed-in human" in r["reasons"][0]
    r = pk.schedule_release(**base, approval=human, final_check={"passed": False, "findings": ["post 1: x"]})
    assert r["status"] == "refused" and "post 1: x" in r["reasons"][0]
    r = pk.schedule_release(**base, approval={"decision": "reject", "decided_by": "vikram"}, final_check=clean)
    assert r["status"] == "refused"
