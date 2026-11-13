"""Competency tests for agents, in code (replaces the old "run() method present" check).

Code competency (fast, no model) — every agent:
  identity         canonical_id and name match the PDF registry (config/agent_registry.yaml)
  governance       gov.certify and gov.modify_finding are denied (except Satya, who certifies)
  escalation       an escalation path exists and returns a request
  tools respond    each declared tool (TOOLS) answers with a status
  behaviour        for agents with code steps in the project chain: known inputs, expected
                   decisions (e.g. Swasthya blocks a cure claim, Vitaran refuses an over-capacity
                   assignment, Prakash refuses unapproved content)

Model competency (thinking agents in the project chain) is run by backend/projects/certification.py:
the agent gets each of its real step instructions and must return the structured answer.

code_hash(agent): the agent's source fingerprint. A certification is valid only for the code it
was given for; changing the agent's code makes it invalid until re-tested and re-certified.
"""
from __future__ import annotations

import hashlib
import inspect
import os
from typing import Callable

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def code_hash(canonical_id: str) -> str | None:
    from agents.base import get_agent_class
    cls = get_agent_class(canonical_id)
    if cls is None:
        return None
    try:
        path = inspect.getsourcefile(cls)
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except (OSError, TypeError):
        return None


def _registry() -> dict:
    with open(os.path.join(ROOT, "config", "agent_registry.yaml"), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    rows = data.get("agents") if isinstance(data, dict) else data
    return {r["canonical_id"]: r for r in rows or []}


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


def _expect(cond: bool, ok: str, bad: str) -> tuple[bool, str]:
    return (True, ok) if cond else (False, bad)


# ---------------------------------------------------------------------------
# behaviour cases for the code steps of the project chain
# ---------------------------------------------------------------------------

POST_OK = {"headline": "World Diabetes Day", "caption": "Walk daily. Consult your doctor for advice about your health.",
           "call_to_action": "Book a sugar check"}


def _swasthya(a):
    bad = a.screen_claims("Our tea is a guaranteed cure.")
    ok = a.screen_claims("Healthy food and daily walks help. Ask your doctor.")
    disc = a.screen_claims("", posts=[{**POST_OK, "caption": "Walk daily."}],
                           required_disclaimers=["Consult your doctor for advice about your health."])
    return _expect(bad["status"] == "block" and ok["status"] == "pass" and disc["status"] == "block",
                   "blocks a cure claim and a missing disclaimer, passes clean copy",
                   f"cure claim -> {bad['status']}, clean -> {ok['status']}, no disclaimer -> {disc['status']}")


def _gopniya(a):
    bad = a.check_privacy("Call 9876543210 about Sunrise Clinic.", ["Sunrise Clinic"])
    ok = a.check_privacy("Free sugar check on Saturday.")
    return _expect(bad["status"] == "block" and ok["status"] == "pass", "finds personal data and other clients",
                   f"personal data -> {bad['status']}, clean -> {ok['status']}")


def _gunvatta(a):
    try:
        a.evaluate_output("text", producer_agent=a.canonical_id)
        return False, "evaluated its own output (independence rule broken)"
    except ValueError:
        pass
    r = a.evaluate_output("x", producer_agent="SAM-AG-082", posts=[POST_OK, {**POST_OK, "headline": "unavailable"}],
                          required_fields=["headline", "caption", "call_to_action"], max_chars=2200)
    return _expect(r["passed"] is False and any("headline is empty" in d for d in r["defects"]),
                   "refuses its own output, finds an incomplete post", f"defects: {r['defects']}")


def _vitaran(a):
    pk = [{"package_id": f"WP-{i}", "type": "social_posts", "sequence": i} for i in (1, 2, 3)]
    over = a.assign_packages(pk, {"social_posts": ["SAM-AG-082"]}, ["SAM-AG-082"], max_per_agent=2)
    inactive = a.assign_packages(pk[:1], {"social_posts": ["SAM-AG-082"]}, [])
    ok = a.assign_packages(pk, {"social_posts": ["SAM-AG-082"]}, ["SAM-AG-082"], max_per_agent=10)
    return _expect(over["status"] == "blocked_unassigned" and inactive["status"] == "blocked_unassigned"
                   and ok["status"] == "assigned",
                   "respects capacity and Active state", f"{over['status']}, {inactive['status']}, {ok['status']}")


def _prakash(a):
    base = dict(client_id="C", content_ref="P", scheduled_time="2026-01-01", channels=["instagram"])
    clean = {"passed": True, "findings": []}
    no = a.schedule_release(**base, approval={"decision": None}, final_check=clean)
    agent = a.schedule_release(**base, approval={"decision": "approve", "decided_by": "SAM-AG-052"}, final_check=clean)
    dirty = a.schedule_release(**base, approval={"decision": "approve", "decided_by": "human"},
                               final_check={"passed": False, "findings": ["x"]})
    ok = a.schedule_release(**base, approval={"decision": "approve", "decided_by": "human"}, final_check=clean)
    return _expect([no["status"], agent["status"], dirty["status"], ok["status"]] ==
                   ["refused", "refused", "refused", "scheduled"],
                   "releases only human-approved, clean content",
                   f"{no['status']}, {agent['status']}, {dirty['status']}, {ok['status']}")


def _anvesh(a):
    lib = {"SRC-T": {"title": "T", "publisher": "P", "url": "https://x",
                     "text": "About 1 in 10 adults worldwide lives with diabetes."}}
    r = a.verify_facts([{"fact": "About 1 in 10 adults lives with diabetes.", "source_id": "SRC-T",
                         "quote": "About 1 in 10 adults worldwide lives with diabetes."},
                        {"fact": "Cinnamon cures diabetes.", "source_id": "SRC-T", "quote": "Cinnamon fully cures diabetes fast."}],
                       lib)
    return _expect([f["verified"] for f in r["facts"]] == [True, False],
                   "verifies only quotes found in the source", f"verified: {[f['verified'] for f in r['facts']]}")


def _smriti(a):
    rs = [a.load_client_context("C", None)["status"],
          a.load_client_context("C", {"status": "draft", "version": 1})["status"],
          a.load_client_context("C", {"status": "approved", "version": 1, "brand_voice": "Warm"})["status"]]
    return _expect(rs == ["missing", "not_approved", "loaded"], "loads only an approved profile", f"{rs}")


def _adhikar(a):
    ok = a.check_many([["SAM-AG-082", "crt.write_copy"]])
    bad = a.check_many([["SAM-AG-082", "gov.certify"]])
    return _expect(ok["status"] == "ready" and bad["status"] != "ready", "denies a permission the agent lacks",
                   f"allowed -> {ok['status']}, forbidden -> {bad['status']}")


def _sankalan(a):
    r = a.build_work_packages("C", {"social_posts": 3})
    return _expect(r["status"] == "planned" and len(r["work_packages"]) == 3, "one package per item in scope",
                   f"{r['status']}, {len(r.get('work_packages') or [])} packages")


def _samay(a):
    pk = [{"package_id": f"WP-{i}", "type": "social_posts", "sequence": i} for i in (1, 2, 3)]
    r = a.schedule_packages(pk, "2026-01-01", 30)
    due = [x.get("due_date") for x in r.get("packages") or []]
    return _expect(len(due) == 3 and all(due) and due == sorted(due) and due[-1] <= "2026-01-31",
                   "dates every package in order within the window", f"due dates {due}")


def _kshamata(a):
    pk = [{"package_id": f"WP-{i}", "type": "social_posts"} for i in (1, 2, 3)]
    warn = a.check_capacity(pk, {"social_posts": ["SAM-AG-082"]}, 2)
    ok = a.check_capacity(pk, {"social_posts": ["SAM-AG-082"]}, 10)
    return _expect(warn["status"] != ok["status"] and ok["status"] == "capacity_ok", "warns when an agent is overloaded",
                   f"over -> {warn['status']}, ok -> {ok['status']}")


def _nirikshan(a):
    r = a.confirm_checks_present({"shuddhi": True}, ["shuddhi", "swasthya"])
    return _expect(r["status"] != "ready", "notices a missing check", f"status {r['status']}")


def _pramaan(a):
    r = a.verify_acceptance("PKG-1", {"shuddhi": True})
    return _expect(not r.get("accepted"), "refuses acceptance with checks missing", f"{r.get('status')}")


def _punargathan(a):
    r1 = a.create_rework_request("X", ["reason"], 1, 3)
    r4 = a.create_rework_request("X", ["reason"], 4, 3)
    return _expect(r1["status"] == "rework_requested" and r4["status"] == "escalate_to_human",
                   "escalates to a human past the round limit", f"{r1['status']}, {r4['status']}")


def _lagaat(a):
    m = {"tokens": 2000, "model_seconds": 3600, "human_decisions": 2, "accepted_deliverables": 4}
    none = a.cost_report(m, {"model_cost_per_1k_tokens": 0.0, "compute_cost_per_model_hour": None,
                             "human_rate_per_hour": None, "review_minutes_per_decision": None})
    full = a.cost_report(m, {"model_cost_per_1k_tokens": 1.0, "compute_cost_per_model_hour": 10.0,
                             "human_rate_per_hour": 600.0, "review_minutes_per_decision": 15})
    return _expect(none["total_cost"] == "unavailable" and full["total_cost"] == 2 + 10 + 300
                   and full["cost_per_accepted_deliverable"] == 78.0,
                   "never guesses a missing rate; computes cost per accepted deliverable",
                   f"{none['total_cost']}, {full['total_cost']}, {full['cost_per_accepted_deliverable']}")


def _lakshya(a):
    r = a.evaluate_kpis({"rework_rounds": 2, "first_pass_rate": 0.9},
                        {"rework_rounds": {"target": 1, "better": "lower"},
                         "first_pass_rate": {"target": 0.7, "better": "higher"}})
    met = {x["kpi"]: x["met"] for x in r["kpis"]}
    return _expect(met == {"rework_rounds": False, "first_pass_rate": True}, "compares KPIs with targets", f"{met}")


BEHAVIOUR: dict[str, list[tuple[str, Callable]]] = {
    "SAM-AG-186": [("blocks unsafe health claims", _swasthya)],
    "SAM-AG-187": [("protects privacy", _gopniya)],
    "SAM-AG-183": [("independent quality check", _gunvatta)],
    "SAM-AG-066": [("assigns only within capacity", _vitaran)],
    "SAM-AG-084": [("release guard", _prakash)],
    "SAM-AG-081": [("verifies facts against sources", _anvesh)],
    "SAM-AG-049": [("approved client facts only", _smriti)],
    "SAM-AG-161": [("permission check", _adhikar)],
    "SAM-AG-064": [("builds work packages", _sankalan)],
    "SAM-AG-065": [("schedules packages", _samay)],
    "SAM-AG-067": [("capacity check", _kshamata)],
    "SAM-AG-062": [("required checks present", _nirikshan)],
    "SAM-AG-072": [("acceptance needs every check", _pramaan)],
    "SAM-AG-071": [("rework round limit", _punargathan)],
    "SAM-AG-146": [("cost per accepted deliverable", _lagaat)],
    "SAM-AG-012": [("KPIs against targets", _lakshya)],
}


# ---------------------------------------------------------------------------
# the suite
# ---------------------------------------------------------------------------

def run_code_tests(canonical_id: str) -> dict:
    """Run every code competency case; returns {passed, cases:[{name, passed, detail}], code_hash}."""
    from agents.base import get_agent_class
    from backend.core.authority import AuthorityError, check_authority
    cases = []

    def case(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"[:300]
        cases.append({"name": name, "passed": bool(ok), "detail": detail})

    from backend.core.message_bus import suppress_publishing
    with suppress_publishing():
        return _run_code_tests(canonical_id, cases, case)


def _run_code_tests(canonical_id: str, cases: list, case) -> dict:
    from agents.base import get_agent_class
    from backend.core.authority import AuthorityError, check_authority
    cls = get_agent_class(canonical_id)
    if cls is None:
        return {"agent_id": canonical_id, "passed": False, "code_hash": None,
                "cases": [{"name": "agent code loads", "passed": False, "detail": "Agent class not registered"}]}
    agent = cls()

    def identity():
        reg = _registry().get(canonical_id)
        if reg is None:
            return False, "not in config/agent_registry.yaml"
        return _expect(cls.canonical_id == reg["canonical_id"] and cls.name == reg["name"],
                       f"{cls.name} matches the registry", f"code says {cls.name}, registry says {reg['name']}")
    case("identity matches the registry", identity)

    def governance():
        if canonical_id == "SAM-AG-010":
            return True, "Satya certifies; governance denials do not apply"
        for perm in ("gov.certify", "gov.modify_finding"):
            try:
                check_authority(canonical_id, perm)
                return False, f"allowed to {perm} (must be denied)"
            except AuthorityError:
                pass
        return True, "may not certify or change findings"
    case("governance limits enforced", governance)

    def escalation():
        fn = getattr(agent, "route_for_approval", None)
        if fn is None:
            return False, "no route_for_approval"
        params = list(inspect.signature(fn).parameters.values())
        kwargs = {p.name: _sample(p) for p in params[2:] if p.default is inspect.Parameter.empty}
        r = fn("other", {"reason": "competency test"}, **kwargs)
        return _expect(isinstance(r, dict) and bool(r), "routes a request to a human", f"returned {r!r}"[:200])
    case("escalation path works", escalation)

    tools = getattr(cls, "TOOLS", None) or {}
    if tools:
        def tools_respond():
            bad = []
            for method, perm in tools.items():
                fn = getattr(agent, method)
                kwargs = {p.name: _sample(p) for p in inspect.signature(fn).parameters.values()
                          if p.default is inspect.Parameter.empty}
                if method == "evaluate_output":
                    kwargs["producer_agent"] = "SAM-AG-082"
                if method == "check_milestone":
                    kwargs["due_iso"] = "2030-01-01T00:00:00Z"
                if method == "record_client_decision":
                    kwargs.update(decision="approve", approver="human")
                if method == "raise_critical_alert":
                    kwargs["severity"] = "S1"
                try:
                    r = fn(**kwargs)
                    if not (isinstance(r, dict) and "status" in r):
                        bad.append(f"{method}: no status")
                except Exception as e:
                    bad.append(f"{method}: {type(e).__name__}")
            return _expect(not bad, f"{len(tools)} tools answer", "; ".join(bad))
        case("declared tools answer", tools_respond)

    for name, fn in BEHAVIOUR.get(canonical_id, []):
        case(name, lambda fn=fn: fn(agent))

    return {"agent_id": canonical_id, "passed": all(c["passed"] for c in cases), "cases": cases,
            "code_hash": code_hash(canonical_id)}
