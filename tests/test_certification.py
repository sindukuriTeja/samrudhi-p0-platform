"""Telemetry, cost and certification."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from agents.base import AgentResult
from backend.core import certification as C
from backend.core import costing, llm
from backend.core.agent_runtime import run_activation_gate
from backend.core.competency import run_code_tests
from backend.database import async_session_maker
from backend.models import ExecutionLog
from backend.models.assurance import Certification
from backend.models.competency import CompetencyRun
from backend.projects import certification as T
from backend.projects.flow import get_flow, step_def
from workers.tasks import MODEL_UNAVAILABLE_ERROR, classify

LEAD = {"username": "satya_human", "role": "assurance_lead"}
FOUNDER = {"username": "vikram", "role": "founder"}


# ---------------------------------------------------------------- telemetry
def test_true_status_is_logged_not_completed():
    down = AgentResult(text="[MODEL UNAVAILABLE] connection refused", agent_id="SAM-AG-082", status="failed")
    assert classify(down, down.text) == ("failed", MODEL_UNAVAILABLE_ERROR)
    bad = AgentResult(text="could not do it", agent_id="SAM-AG-082", status="failed")
    assert classify(bad, bad.text)[0] == "failed"
    assert classify(AgentResult(text="", agent_id="x"), "")[0] == "failed"
    assert classify(AgentResult(text="Escalated to Arjun", agent_id="x", status="escalated"), "Escalated")[0] == "escalated"
    assert classify(AgentResult(text="Done.", agent_id="x"), "Done.") == ("completed", None)


async def test_model_usage_is_collected_per_run(monkeypatch):
    async def fake_post(self, url, json=None, **kw):
        return httpx.Response(200, json={"response": '{"a": 1}', "prompt_eval_count": 120, "eval_count": 30},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    calls, token = llm.start_usage()
    await llm.generate("hello", format="json")
    await llm.generate("again")
    llm.stop_usage(token)
    u = llm.usage_summary(calls)
    assert (u["model_calls"], u["prompt_tokens"], u["response_tokens"]) == (2, 240, 60)
    await llm.generate("not measured")                       # outside a run nothing is collected
    assert len(calls) == 2

    async def failing(self, url, json=None, **kw):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx.AsyncClient, "post", failing)
    calls, token = llm.start_usage()
    with pytest.raises(httpx.ConnectError):
        await llm.generate("x")
    llm.stop_usage(token)
    assert llm.usage_summary(calls)["model_failures"] == 1


# ---------------------------------------------------------------- cost and KPIs
def test_cost_never_guesses_a_missing_rate():
    m = {"tokens": 30000, "model_seconds": 1800, "human_decisions": 2, "accepted_deliverables": 3}
    r = costing.cost(m, {"model_cost_per_1k_tokens": 0.0, "compute_cost_per_model_hour": None,
                         "human_rate_per_hour": None, "review_minutes_per_decision": None}, "INR")
    assert r["total_cost"] == "unavailable" and r["cost_per_accepted_deliverable"] == "unavailable"
    assert r["tokens_per_accepted_deliverable"] == 10000 and r["model_minutes_per_accepted_deliverable"] == 10.0
    full = costing.cost(m, {"model_cost_per_1k_tokens": 0.5, "compute_cost_per_model_hour": 40,
                            "human_rate_per_hour": 900, "review_minutes_per_decision": 10}, "INR")
    assert full["parts"] == {"model_tokens": 15.0, "compute": 20.0, "human_review": 300.0}
    assert full["total_cost"] == 335.0 and full["cost_per_accepted_deliverable"] == pytest.approx(111.6667)
    none = costing.cost({**m, "accepted_deliverables": 0}, None)
    assert none["cost_per_accepted_deliverable"] == "unavailable" and "Gate 2" in none["note"]


def test_kpis_are_compared_with_targets_in_code():
    r = costing.evaluate({"first_pass_rate": 0.5, "rework_rounds": 1, "on_time_rate": None})
    by = {k["kpi"]: k["met"] for k in r["kpis"]}
    assert by["first_pass_rate"] is False and by["rework_rounds"] is True and by["on_time_rate"] is None
    assert r["status"] == "off_target" and "first_pass_rate" in r["missed"]


# ---------------------------------------------------------------- competency tests
def test_every_agent_passes_its_code_competency_tests():
    from agents.base import _REGISTRY, load_all
    load_all()
    failed = {cid: [c for c in run_code_tests(cid)["cases"] if not c["passed"]] for cid in _REGISTRY}
    assert {k: v for k, v in failed.items() if v} == {}


def test_competency_tests_catch_a_wrong_decision(monkeypatch):
    from agents.base import get_agent_class
    cls = get_agent_class("SAM-AG-186")
    monkeypatch.setattr(cls, "HIGH_RISK_CLAIMS", ())           # Swasthya "forgets" its blocked claims
    r = run_code_tests("SAM-AG-186")
    bad = [c for c in r["cases"] if not c["passed"]]
    assert not r["passed"] and bad[0]["name"] == "blocks unsafe health claims"


async def test_code_tests_send_no_real_events():
    from backend.models import BusEvent
    async with async_session_maker() as s:
        before = len((await s.execute(select(BusEvent.id))).scalars().all())
    assert run_code_tests("SAM-AG-192")["passed"]               # Sankat raises a critical alert in its tools
    async with async_session_maker() as s:
        assert len((await s.execute(select(BusEvent.id))).scalars().all()) == before


def test_model_answer_checks():
    flow = get_flow()
    writing, shuddhi = step_def(flow, "writing"), step_def(flow, "shuddhi")
    good = json.dumps({"posts": T.POSTS})
    assert T.check_answer(writing, good) == (True, "structured answer accepted")
    assert not T.check_answer(writing, json.dumps({"posts": T.POSTS[:1]}))[0]          # wrong count
    assert not T.check_answer(writing, "Sure! Here are your posts.")[0]               # not JSON
    blank = json.dumps({"posts": [{"headline": "unavailable", "caption": "unavailable", "call_to_action": "unavailable"}] * 2})
    assert T.check_answer(writing, blank)[1] == "every field is empty or unavailable"
    verdict = {"issues": [], "verdict": "maybe", "reasons": "x"}
    assert "not pass or send_back" in T.check_answer(shuddhi, json.dumps(verdict))[1]


async def test_model_tests_run_the_real_step_instructions(monkeypatch):
    seen = []

    async def fake_dispatch(args, kwargs, on_ref):
        seen.append((args, kwargs))
        d = next(x for x in C.model_steps_for(args[0]) if x["tag"] == kwargs["context"]["step"])
        return {"status": "completed", "output": json.dumps(T.SAMPLE_INPUTS.get(d["key"]) or {"posts": T.POSTS}),
                "tokens_used": 500, "telemetry": {"model_seconds": 12.5}}
    monkeypatch.setattr(T.dispatcher, "dispatch", fake_dispatch)
    r = await T.run_model("SAM-AG-082", "satya_human")                              # Lekha: the writing step
    assert r["passed"] and r["tokens"] == 500 and r["model_seconds"] == 12.5
    args, kwargs = seen[0]
    assert "Write the copy for every post" in args[1] and kwargs["output_format"] == "json"
    assert kwargs["context"]["work_packages"] and args[2] == T.TENANT

    async def down(args, kwargs, on_ref):
        return {"status": "failed", "error": MODEL_UNAVAILABLE_ERROR}
    monkeypatch.setattr(T.dispatcher, "dispatch", down)
    r = await T.run_model("SAM-AG-082", "satya_human")
    assert not r["passed"] and r["cases"][0]["detail"].startswith("Model unavailable")


# ---------------------------------------------------------------- certification and the gate
async def _model_evidence(cid, passed=True):
    from backend.core.competency import code_hash
    async with async_session_maker() as s:
        s.add(CompetencyRun(run_id=f"CMP-{uuid.uuid4().hex[:6].upper()}", agent_id=cid, kind="model", status="done",
                            passed=passed, cases=[], code_hash=code_hash(cid), run_by="satya_human",
                            started_at=datetime.now(timezone.utc), ended_at=datetime.now(timezone.utc)))
        await s.commit()


async def test_gate_needs_tests_and_a_human_certification(monkeypatch):
    cid = "SAM-AG-081"                                          # Anvesh: a thinking agent with a model step
    async with async_session_maker() as s:
        gate = await run_activation_gate(s, cid)
    assert not gate.passed and "no valid certification" in " ".join(gate.failures)

    await T.run_code(cid, "satya_human")
    async with async_session_maker() as s:
        with pytest.raises(C.CertificationError) as e:
            await C.certify(s, cid, LEAD)                       # model evidence missing
        assert "model tests: not tested" in str(e.value)
    await _model_evidence(cid)
    async with async_session_maker() as s:
        with pytest.raises(C.CertificationError) as e:
            await C.certify(s, cid, FOUNDER)                    # only an assurance lead certifies
        assert "Only an assurance lead" in str(e.value)
        cert = await C.certify(s, cid, LEAD)
        assert cert.level == "C2" and cert.human_confirmed and cert.conditions[0]["certified_by"] == "satya_human"
        gate = await run_activation_gate(s, cid)
    assert gate.passed, gate.failures

    # the agent's code changes: the certification no longer holds
    monkeypatch.setattr(C, "code_hash", lambda _cid: "changed-code")
    async with async_session_maker() as s:
        v = await C.validity(s, cid)
    assert not v["valid"] and "code changed" in v["reason"]
    monkeypatch.undo()

    async with async_session_maker() as s:
        await C.revoke(s, cid, LEAD, "Wrong facts in a live run")
        v = await C.validity(s, cid)
        assert not v["valid"] and "revoked by satya_human" in v["reason"]
        assert not (await run_activation_gate(s, cid)).passed


async def test_expired_or_failed_evidence_is_not_enough():
    cid = "SAM-AG-064"                                          # Sankalan: code steps only -> C1
    await T.run_code(cid, "satya_human")
    async with async_session_maker() as s:
        cert = await C.certify(s, cid, LEAD)
        assert cert.level == "C1"
        cert.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await s.commit()
        assert "expired" in (await C.validity(s, cid))["reason"]
    await _model_evidence("SAM-AG-082", passed=False)
    await T.run_code("SAM-AG-082", "satya_human")
    async with async_session_maker() as s:
        with pytest.raises(C.CertificationError) as e:
            await C.certify(s, "SAM-AG-082", LEAD)
        assert "last test failed" in str(e.value)


# ---------------------------------------------------------------- measuring a project
async def test_metrics_use_the_execution_log(monkeypatch):
    from backend.models.projects import Project
    from backend.projects.metrics import project_metrics
    pid = f"PRJ-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    async with async_session_maker() as s:
        s.add(Project(id=pid, name="m", client_id="TEST", flow_key="documented_chain", status="running",
                      created_by="t", started_at=now - timedelta(hours=2)))
        for i, (status, tok, secs) in enumerate([("completed", 1000, 40.0), ("completed", 800, 30.0), ("failed", 0, 0.0)]):
            s.add(ExecutionLog(execution_id=f"exec-m-{pid}-{i}", agent_id="SAM-AG-082", workflow_id=pid, task="t",
                               tenant_id="TEST", status=status, tokens_used=tok, prompt_tokens=tok - 100 if tok else 0,
                               response_tokens=100 if tok else 0, latency_s=secs + 5, started_at=now, ended_at=now,
                               trace_id="t", raw_result={"telemetry": {"model_seconds": secs}}))
        await s.commit()
        m = await project_metrics(s, pid)
    assert (m["model_runs"], m["model_failures"], m["tokens"], m["response_tokens"]) == (3, 1, 1800, 200)
    assert m["model_seconds"] == 70.0 and m["model_failure_rate"] == pytest.approx(0.333)
    assert 1.9 < m["cycle_time_hours"] < 2.1 and m["accepted_deliverables"] == 0 and m["on_time_rate"] is None
