"""Tests for the Control Room project flow: the documented chain (How a Project Runs).

Model steps are replaced with a stub so no model or worker is needed. Code steps run the
agents' real tools (Sankalan, Swasthya, Gopniya, Pramaan, Sweekriti, Lagaat, ...).
"""
import pytest
from sqlalchemy import select

from backend.database import async_session_maker
from backend.models import Agent, Approval
from backend.models.projects import ApprovalDecision, Project, ProjectStep  # registers tables
from backend.projects import queries as Q
from backend.projects import runner as R
from backend.projects.flow import get_flow, required_agents, step_keys
from backend.projects.readable import one_line, readable


# ---------------------------------------------------------------------------
# readable text
# ---------------------------------------------------------------------------

def test_readable_turns_json_into_lines():
    out = readable('{"caption_one": "Eat well", "sources": ["WHO", "CDC"], "verified": true}')
    assert "{" not in out and "Caption one: Eat well" in out and "• WHO" in out and "Verified: yes" in out


def test_readable_drops_code_blocks_and_markdown():
    out = readable("## Plan\n**Three** posts\n```python\nprint('x')\n```\n- item `one`")
    assert "print" not in out and "```" not in out and "#" not in out and "**" not in out
    assert "Three posts" in out and "• item one" in out


def test_one_line_prefers_a_sentence_over_a_heading():
    assert one_line("Client Brief Capture\n\nThe brand tone is calm and reassuring. More.") == \
        "The brand tone is calm and reassuring."


# ---------------------------------------------------------------------------
# the documented chain
# ---------------------------------------------------------------------------

FLOW = get_flow()
FLOW_AGENTS = required_agents(FLOW)


def test_flow_follows_the_document_order():
    keys = step_keys(FLOW)
    assert keys[0] == "start_check" and keys[1] == "kickoff" and keys[-1] == "final_brief"
    order = ["kickoff", "client_expectations", "client_context", "brief", "workflow", "delivery_plan",
             "work_packages", "schedule", "resources", "capacity", "assignments", "pipeline",
             "creative_request", "research", "direction", "calendar", "distribution", "writing",
             "design_brief", "artwork", "shuddhi", "pariksha", "gunvatta", "swasthya", "gopniya",
             "nirikshan", "pramaan", "sweekriti", "client_update", "publishing", "client_report",
             "costing", "intelligence", "kpi_status", "review_notes", "close_actions", "final_brief"]
    positions = [keys.index(k) for k in order]
    assert positions == sorted(positions)
    agents = {s["key"]: s["agent"] for s in FLOW["steps"]}
    assert agents["kickoff"] == agents["final_brief"] == "SAM-AG-001"          # Arjun opens and closes
    assert agents["actions"] == agents["close_actions"] == "SAM-AG-013"        # Samanvay twice
    gates = [s["key"] for s in FLOW["steps"] if s.get("approval")]
    assert gates == ["distribution", "sweekriti"]                             # Gate 1 and Gate 2


async def _ensure_agents(status: str) -> None:
    async with async_session_maker() as s:
        existing = {a.canonical_id: a for a in (await s.execute(
            select(Agent).where(Agent.canonical_id.in_(FLOW_AGENTS)))).scalars().all()}
        for cid in FLOW_AGENTS:
            a = existing.get(cid)
            if a is None:
                s.add(Agent(canonical_id=cid, name=cid, designation="Test agent", position_id=f"T-{cid[-3:]}",
                            department="Test", department_code="TST", stage="P1-P2",
                            human_owner="test", technical_custodian="test", evaluator="test",
                            autonomy="bounded", priority="P1", agent_type="thinking",
                            target_competency="C3", status=status))
            else:
                a.status = status
        await s.commit()


async def _new_project(name="Test project", client_id="TEST", profile=True) -> str:
    """A draft project; by default its client has an approved profile in the knowledge store."""
    from backend.projects.common import new_project_id
    from backend.models.knowledge import ClientProfile
    pid = new_project_id()
    async with async_session_maker() as s:
        if profile and await s.get(ClientProfile, client_id) is None:
            s.add(ClientProfile(client_id=client_id, name="Test Hospital", brand_voice="Calm and clear",
                                audience="Adults 35-60", services=["Diabetes clinic"], locations=["Hyderabad"],
                                key_messages=["Early checks help"], status="approved", version=1,
                                updated_by="editor", approved_by="approver"))
        s.add(Project(id=pid, name=name, client_id=client_id, flow_key="documented_chain",
                      status="draft", created_by="tester"))
        await s.commit()
    return pid


@pytest.fixture
def no_kick(monkeypatch):
    monkeypatch.setattr(R.runner, "kick", lambda *a, **k: None)


import json
import re

from backend.projects.flow import step_def

TAG_TO_KEY = {s["tag"]: s["key"] for s in FLOW["steps"]}


def _fill(spec, key, count, writer_text):
    """Build an answer that matches a step's output schema (what a well-behaved model returns)."""
    if isinstance(spec, dict):
        return {k: _fill(v, k, count, writer_text) for k, v in spec.items()}
    if isinstance(spec, list):
        n = count if key in ("posts", "pieces", "briefs", "specs") and count else 1
        items = [_fill(spec[0], key, count, writer_text) for _ in range(n)]
        if key == "posts":                      # a real writer gives every post its own caption
            for i, item in enumerate(items, start=1):
                if isinstance(item, dict) and "caption" in item:
                    item["caption"] = f"Post {i}. {item['caption']}"
        return items
    if spec == "bool":
        return True
    if key == "caption":
        return writer_text
    return f"Plain words for {key}."


def stub(monkeypatch, writer_text="Eat well and walk daily. Ask your doctor about a sugar check.",
         verdicts=None, seen=None, broken=None, answers=None):
    """Replace model steps with schema-valid JSON.

    verdicts: {agent: ["send_back: reasons", ...]} consumed in order (default pass).
    broken:   {agent: n} -> the first n answers of that agent are not valid JSON.
    """
    verdicts = {k: list(v) for k, v in (verdicts or {}).items()}
    broken = dict(broken or {})

    async def fake_dispatch(args, kwargs, on_ref):
        await on_ref("test")
        agent, task = args[0], args[1]
        if seen is not None:
            seen.setdefault(agent, []).append((task, kwargs.get("context", {})))
        if broken.get(agent):
            broken[agent] -= 1
            return {"status": "completed", "execution_id": f"exec-test-{agent}", "output": "Sure! Here is my answer."}
        d = step_def(FLOW, TAG_TO_KEY[kwargs["context"]["step"]])
        m = re.search(r"must contain exactly (\d+) items", task)
        text = writer_text() if callable(writer_text) else writer_text
        data = _fill(d["output"], "", int(m.group(1)) if m else 0, text)
        if answers and agent in answers:                 # a specific answer for this agent
            data = json.loads(json.dumps(answers[agent]))
        if d.get("verdict"):
            queue = verdicts.get(agent) or []
            v = queue.pop(0) if queue else "pass"
            data["verdict"], _, reason = v.partition(":")
            data["reasons"] = reason.strip() or "No problems found."
        assert kwargs.get("output_format") == "json"
        return {"status": "completed", "execution_id": f"exec-test-{agent}", "output": json.dumps(data)}
    monkeypatch.setattr(R.dispatcher, "dispatch", fake_dispatch)


async def run_until_blocked(pid):
    while await R.runner._advance(pid):
        pass
    return await Q.project_state(pid)


def steps_of(st, key):
    return [x for x in st["steps"] if x["step_key"] == key]


async def test_start_refused_when_agents_not_active(no_kick):
    await _ensure_agents("proposed")
    pid = await _new_project()
    with pytest.raises(R.ProjectError) as e:
        await R.start_project(pid, "go", "tester")
    assert e.value.status == 409
    assert {a["canonical_id"] for a in e.value.detail["not_active"]} == set(FLOW_AGENTS)


async def test_start_creates_every_chain_step_once(no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, "Make 3 posts", "tester")
    with pytest.raises(R.ProjectError):
        await R.start_project(pid, "again", "tester")
    st = await Q.project_state(pid)
    assert [x["step_key"] for x in st["steps"]] == step_keys(FLOW)
    assert st["steps"][1]["block"] == 2 and st["steps"][1]["block_label"] == "Kick-off"


async def test_inactive_agent_is_never_dispatched(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, None, "tester")
    async with async_session_maker() as s:
        arjun = (await s.execute(select(Agent).where(Agent.canonical_id == "SAM-AG-001"))).scalars().first()
        arjun.status = "restricted"
        await s.commit()

    async def boom(*a, **k):
        raise AssertionError("an inactive agent must not be dispatched")
    monkeypatch.setattr(R.dispatcher, "dispatch", boom)
    st = await run_until_blocked(pid)
    assert st["project"]["status"] == "needs_attention"
    kick = steps_of(st, "kickoff")[0]
    assert kick["status"] == "needs_attention" and "not Active" in kick["error"]
    assert steps_of(st, "start_check")[0]["status"] == "completed"   # Adhikar's code check ran
    await _ensure_agents("active")


async def test_full_chain_with_both_gates(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    seen = {}
    stub(monkeypatch, seen=seen)
    await R.start_project(pid, "Create 4 short posts about early signs of diabetes.", "tester")

    st = await run_until_blocked(pid)
    gate1 = st["pending_approval"]
    assert gate1 and gate1["agent_id"] == "SAM-AG-079" and gate1["why"]              # Tarangini, Gate 1
    packages = steps_of(st, "work_packages")[0]["result"]
    assert packages["package_count"] == 4                                             # scope from the message
    assert steps_of(st, "assignments")[0]["result"]["status"] == "assigned"
    assert steps_of(st, "capacity")[0]["result"]["status"] == "capacity_ok"

    await R.decide(pid, gate1["request_id"], "approve_with_changes", "Make the tone warmer.", "tester")
    st = await Q.project_state(pid)
    assert [x["round"] for x in steps_of(st, "direction")] == [1, 2]
    assert [x["round"] for x in steps_of(st, "distribution")] == [1, 2]
    st = await run_until_blocked(pid)
    disha_round2_task, disha_ctx = seen["SAM-AG-076"][-1]
    assert "Make the tone warmer." in disha_round2_task
    # structured hand-over: Disha receives Shruti's whole brief record and Anvesh's research record
    records = {h["step"]: h for h in disha_ctx["handed_over"]}
    assert set(records["Client brief"]["record"]) == {"objective", "audience", "deliverables", "deadline", "limits"}
    assert isinstance(records["Research"]["record"]["facts"], list)

    gate1b = st["pending_approval"]
    assert gate1b["agent_id"] == "SAM-AG-079"
    await R.decide(pid, gate1b["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)

    gate2 = st["pending_approval"]
    assert gate2 and gate2["agent_id"] == "SAM-AG-052"                                # Sweekriti, Gate 2
    assert steps_of(st, "pramaan")[0]["result"]["accepted"] is True
    assert steps_of(st, "swasthya")[0]["result"]["status"] == "pass"
    await R.decide(pid, gate2["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)

    assert st["project"]["status"] == "completed"
    skipped = [x["step_key"] for x in st["steps"] if x["status"] == "skipped"]
    assert skipped == ["data_collection", "data_cleaning", "data_matching", "kpi_values", "performance", "dashboards"]
    assert all(x["summary"] for x in st["steps"] if x["status"] == "skipped")       # every skip has a reason
    cost = steps_of(st, "costing")[0]["result"]
    assert cost["accepted_deliverables"] == 4 and cost["total_cost"] == "unavailable"
    assert steps_of(st, "final_brief")[0]["status"] == "completed"
    summary = await Q.summary(pid)
    assert {d["name"] for d in summary["deliverables"]} >= {"Copy", "Design brief", "Client report"}


async def test_claim_check_sends_work_back_and_stops_at_round_limit(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    seen = {}
    stub(monkeypatch, writer_text="This tea is a guaranteed cure for diabetes.", seen=seen)
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")   # Gate 1
    st = await run_until_blocked(pid)

    rework = steps_of(st, "rework")
    assert len(rework) == 4                                       # 3 allowed rounds + the one that escalates
    assert rework[-1]["status"] == "needs_attention" and "Round limit" in rework[-1]["error"]
    assert [x["round"] for x in steps_of(st, "writing")] == [1, 2, 3, 4]
    shuddhi = steps_of(st, "shuddhi")                             # the code rules catch it first,
    assert all(not x["passed"] for x in shuddhi)                  # whatever the model said
    assert all("guaranteed cure" in " ".join(x["result"]["code_check"]["findings"]) for x in shuddhi)
    assert shuddhi[0]["result"]["model_verdict"].startswith("pass")
    assert not any(x["status"] == "completed" for x in steps_of(st, "swasthya"))
    assert st["project"]["status"] == "needs_attention"
    lekha_round2_task, ctx = seen["SAM-AG-082"][1]
    assert "guaranteed cure" in lekha_round2_task and ctx["revision_note"]
    assert not steps_of(st, "sweekriti")[0]["approval_id"]        # never reached Gate 2


async def test_shuddhi_send_back_then_pass(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch, verdicts={"SAM-AG-080": ["send_back: caption 2 claims too much"]})
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)
    shuddhi = steps_of(st, "shuddhi")
    assert [x["passed"] for x in shuddhi] == [False, True]
    assert "caption 2" in shuddhi[0]["result"]["reasons"]
    assert len(steps_of(st, "rework")) == 1 and steps_of(st, "rework")[0]["status"] == "completed"
    assert st["pending_approval"]["agent_id"] == "SAM-AG-052"     # reached Gate 2 after the fix


async def test_reject_at_gate2_then_retry_reruns_the_checks(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch)
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)
    gate2 = st["pending_approval"]
    await R.decide(pid, gate2["request_id"], "reject", "Too salesy.", "tester")
    with pytest.raises(R.ProjectError) as again:
        await R.decide(pid, gate2["request_id"], "approve", None, "tester")
    assert again.value.status == 409
    st = await Q.project_state(pid)
    assert st["project"]["status"] == "needs_attention"
    rejected = next(x for x in st["steps"] if x["approval_id"] == gate2["request_id"])
    await R.retry_step(pid, rejected["id"], "tester")
    st = await run_until_blocked(pid)
    for key in ("writing", "shuddhi", "swasthya", "pramaan", "sweekriti"):
        assert len(steps_of(st, key)) == 2, key
    async with async_session_maker() as s:
        dec = (await s.execute(select(ApprovalDecision).where(
            ApprovalDecision.request_id == gate2["request_id"]))).scalars().first()
    assert dec.decision == "reject" and dec.note == "Too salesy."


async def test_model_unavailable_is_reported_not_invented(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, None, "tester")

    async def down(args, kwargs, on_ref):
        await on_ref("test")
        return {"status": "completed", "execution_id": "exec-down",
                "output": "[MODEL UNAVAILABLE] connection refused. Arjun cannot produce output."}
    monkeypatch.setattr(R.dispatcher, "dispatch", down)
    st = await run_until_blocked(pid)
    kick = steps_of(st, "kickoff")[0]
    assert kick["status"] == "needs_attention" and kick["error"].startswith("Model unavailable")
    assert not any(m["author_type"] == "agent" and m["agent_id"] == "SAM-AG-001" for m in st["messages"])


async def test_activate_needed_uses_the_gate(no_kick):
    await _ensure_agents("proposed")
    result = await R.activate_needed("tester")
    assert result["activated"] >= 1
    ready = await R.readiness()
    # every agent that passed the gate is now Active; any that failed is listed with a reason
    assert {f["canonical_id"] for f in result["failed"]} == {a["canonical_id"] for a in ready["not_active"]}
    await _ensure_agents("active")


async def test_wrong_structure_is_asked_again_then_accepted(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch, broken={"SAM-AG-001": 1})
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    kick = steps_of(st, "kickoff")
    assert len(kick) == 1 and kick[0]["status"] == "completed"
    assert set(kick[0]["result"]) >= {"goal", "priority", "deadline", "owners", "risks"}
    assert any(m["kind"] == "format" for m in st["messages"])     # the "asking again" note


async def test_wrong_structure_twice_stops_the_step(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch, broken={"SAM-AG-001": 2})
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    kick = steps_of(st, "kickoff")[0]
    assert kick["status"] == "needs_attention" and "required structure" in kick["error"]


async def test_wrong_number_of_posts_is_rejected(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch)
    await R.start_project(pid, "Make 2 posts.", "tester")
    st = await run_until_blocked(pid)                          # Gate 1
    from backend.projects.schema import validate
    cal = steps_of(st, "calendar")[0]["result"]
    assert len(cal["posts"]) == 2 and not validate(cal, step_def(FLOW, "calendar")["output"])


async def test_completed_project_is_saved_to_the_registers(monkeypatch, no_kick):
    from backend.models import (Action, Allocation, ApprovalWorkflow, Brief, ClientCommunication,
                                ContentCalendar, ContentPackage, ContentStrategy, Initiative, QaReview,
                                Report, WorkPackage, WorkflowInstance)
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch)
    await R.start_project(pid, "Create 3 posts for World Diabetes Day.", "tester")
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)
    gate2 = st["pending_approval"]
    await R.decide(pid, gate2["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)
    assert st["project"]["status"] == "completed"

    async with async_session_maker() as s:
        one = lambda q: s.execute(q)
        wf = (await one(select(WorkflowInstance).where(WorkflowInstance.workflow_id == pid))).scalars().first()
        assert wf.status == "delivered"
        assert [x["to"] for x in wf.stages] == ["planning", "allocated", "executing", "quality", "approved", "delivered"]
        assert (await one(select(Initiative).where(Initiative.objective_ref == pid))).scalars().first().milestones
        wps = (await one(select(WorkPackage).where(WorkPackage.workflow_id == wf.id))).scalars().all()
        assert len(wps) == 3 and all(w.deadline and w.assigned_agent == "SAM-AG-082" for w in wps)
        assert {w.status for w in wps} == {"delivered"}
        allocs = (await one(select(Allocation).where(Allocation.decision_ref == pid))).scalars().all()
        assert len(allocs) == 9                                      # 3 packages x Lekha, Roop, Chitra
        assert (await one(select(ContentStrategy).where(ContentStrategy.strategy_id == f"STR-{pid}-R1"))).scalars().first()
        cal = (await one(select(ContentCalendar).where(ContentCalendar.calendar_id == f"CAL-{pid}-R1"))).scalars().first()
        assert len(cal.items) == 3
        pkgs = (await one(select(ContentPackage).where(ContentPackage.package_id.like(f"CP-{pid}-%")))).scalars().all()
        assert len(pkgs) == 3 and {p.status for p in pkgs} == {"scheduled"}
        reviews = (await one(select(QaReview).where(QaReview.package_id.in_([p.id for p in pkgs])))).scalars().all()
        assert {r.reviewer for r in reviews} == {"SAM-AG-080", "SAM-AG-094", "SAM-AG-183", "SAM-AG-186", "SAM-AG-187"}
        aw = (await one(select(ApprovalWorkflow).where(ApprovalWorkflow.approval_id == gate2["request_id"]))).scalars().first()
        assert aw.status == "approved"
        assert (await one(select(ClientCommunication).where(ClientCommunication.comm_id == f"COM-{pid}-R1"))).scalars().first()
        rpt = (await one(select(Report).where(Report.report_id == f"RPT-{pid}-R1"))).scalars().first()
        assert rpt and rpt.source_trace
        acts = (await one(select(Action).where(Action.task.like(f"[{pid}]%")))).scalars().all()
        assert acts and {a.status for a in acts} == {"closed"}
        briefs = (await one(select(Brief).where(Brief.brief_type == "project"))).scalars().all()
        assert any(b.content.get("project_id") == pid for b in briefs)
    saved = {r["table"] for x in st["steps"] for r in x["saved"]}
    assert {"initiatives", "workflow_instances", "work_packages", "allocations", "content_strategies",
            "content_calendars", "content_packages", "qa_reviews", "approval_workflows",
            "client_communications", "reports", "briefs", "actions"} <= saved


async def test_research_is_never_marked_verified_without_a_source(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch)                                    # the stub model claims verified: true
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    research = steps_of(st, "research")[0]["result"]
    assert research["facts"] and all(f["verified"] is False for f in research["facts"])
    assert research["facts"][0]["reason"] == "not from an approved source in the library"
    assert research["sources_available"] == 0
    msg = next(m for m in st["messages"] if m["step_tag"] == "Research")
    assert msg["text"].startswith("Facts are checked in code against the approved source library")


# ---------------------------------------------------------------------------
# planning agents drive the run
# ---------------------------------------------------------------------------

from backend.projects.flow import _load as _load_flows


def _defaults():
    return _load_flows()["flows"]["documented_chain"]["defaults"]


async def test_producers_get_exactly_the_planned_packages(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    seen = {}
    stub(monkeypatch, seen=seen)
    await R.start_project(pid, "Make 4 posts for World Diabetes Day.", "tester")
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)                                        # Gate 2

    planned = {p["package_id"]: p["due_date"] for p in steps_of(st, "schedule")[0]["result"]["packages"]}
    assert len(planned) == 4
    for agent in ("SAM-AG-082", "SAM-AG-078", "SAM-AG-083"):                 # Lekha, Roop, Chitra
        task, ctx = seen[agent][0]
        got = {p["package_id"]: p["due_date"] for p in ctx["work_packages"]}
        assert got == planned                                                # Sankalan's ids, Samay's dates
        assert "assigned 4 work package" in task
    assert len(steps_of(st, "writing")[0]["result"]["posts"]) == 4
    pipe = [m["text"] for m in st["messages"] if m["kind"] == "pipeline"]
    assert len(pipe) == 1 and "SAM-AG-082 (4 package(s)), then SAM-AG-078 (4 package(s)), then SAM-AG-083" in pipe[0]
    assert steps_of(st, "pipeline")[0]["result"]["status"] == "defined"


async def test_producer_without_packages_is_skipped_and_not_reworked(monkeypatch, no_kick):
    await _ensure_agents("active")
    monkeypatch.setitem(_defaults()["routing"], "social_posts", ["SAM-AG-082", "SAM-AG-078"])   # no Chitra
    pid = await _new_project()
    stub(monkeypatch, verdicts={"SAM-AG-080": ["send_back: caption 1 needs a source"]})
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)
    art = steps_of(st, "artwork")
    assert len(art) == 1 and art[0]["status"] == "skipped" and "no work packages" in art[0]["summary"]
    assert [x["round"] for x in steps_of(st, "writing")] == [1, 2]           # rework round happened
    assert st["pending_approval"]["agent_id"] == "SAM-AG-052"               # Gate 2 still reached


async def test_capacity_limit_leaves_packages_unassigned(monkeypatch, no_kick):
    await _ensure_agents("active")
    monkeypatch.setitem(_defaults(), "max_per_agent", 2)
    pid = await _new_project()
    stub(monkeypatch)
    await R.start_project(pid, "Make 3 posts.", "tester")
    st = await run_until_blocked(pid)
    cap = steps_of(st, "capacity")[0]["result"]
    assert cap["status"] == "capacity_warning"                               # Kshamata warned
    asg = steps_of(st, "assignments")[0]
    assert asg["status"] == "needs_attention" and "at capacity (2)" in asg["error"]
    assert st["project"]["status"] == "needs_attention"
    assert not steps_of(st, "writing")[0]["started_at"]                      # production never started


async def test_inactive_producer_is_not_assigned(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch)
    await R.start_project(pid, None, "tester")
    async with async_session_maker() as s:
        chitra = (await s.execute(select(Agent).where(Agent.canonical_id == "SAM-AG-083"))).scalars().first()
        chitra.status = "restricted"
        await s.commit()
    st = await run_until_blocked(pid)
    asg = steps_of(st, "assignments")[0]
    assert asg["status"] == "needs_attention" and "SAM-AG-083 is not Active" in asg["error"]
    await _ensure_agents("active")


# ---------------------------------------------------------------------------
# safety rules in code
# ---------------------------------------------------------------------------

from backend.core import safety_rules as SR

DISCLAIMER = "Consult your doctor for advice about your health."


def _writer(seen, first, later):
    """Lekha's caption: `first` in round 1, `later` from round 2 on."""
    return lambda: first if len(seen.get("SAM-AG-082", [])) <= 1 else later


async def _to_gate2(pid):
    st = await run_until_blocked(pid)
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")   # Gate 1
    return await run_until_blocked(pid)


async def test_client_disclaimer_is_given_to_the_writer_and_enforced(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project(client_id="DEMO-HEALTHCARE-01")
    seen = {}
    stub(monkeypatch, seen=seen, writer_text=_writer(seen, "Walk daily.", f"Walk daily. {DISCLAIMER}"))
    await R.start_project(pid, None, "tester")
    st = await _to_gate2(pid)

    task, ctx = seen["SAM-AG-082"][0]
    assert DISCLAIMER in ctx["safety_rules"] and "Client safety rules" in task
    sw = steps_of(st, "swasthya")
    assert sw[0]["result"]["status"] == "block"
    assert any("required disclaimer missing" in x for x in sw[0]["result"]["findings"])
    assert sw[1]["result"]["status"] == "pass" and sw[1]["round"] == 2
    assert st["pending_approval"]["agent_id"] == "SAM-AG-052"                 # Gate 2 after the fix

    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")   # Gate 2
    st = await run_until_blocked(pid)
    pub = steps_of(st, "publishing")[-1]["result"]
    assert pub["status"] == "scheduled"
    assert st["project"]["status"] == "completed"


async def test_code_rules_overrule_a_pass_from_the_model(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    seen = {}
    stub(monkeypatch, seen=seen, writer_text=_writer(seen, "Visit the best hospital in town.", "Walk daily."))
    await R.start_project(pid, None, "tester")
    st = await _to_gate2(pid)
    shuddhi = steps_of(st, "shuddhi")
    assert shuddhi[0]["passed"] is False                                       # the model said pass
    assert shuddhi[0]["result"]["model_verdict"].startswith("pass")
    assert any(r.startswith("Code rule: post 1: superiority claim") for r in shuddhi[0]["result"]["reasons"])
    assert shuddhi[1]["passed"] is True and shuddhi[1]["result"]["code_check"]["passed"] is True
    assert st["pending_approval"]["agent_id"] == "SAM-AG-052"


async def test_statistic_not_in_the_research_is_sent_back(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    seen = {}
    stub(monkeypatch, seen=seen, writer_text=_writer(seen, "40% of adults do not know they have diabetes.",
                                                     "Many adults do not know they have diabetes."))
    await R.start_project(pid, None, "tester")
    st = await _to_gate2(pid)
    found = steps_of(st, "shuddhi")[0]["result"]["code_check"]["findings"]
    assert 'post 1: figure "40%" is not in the research pack' in found
    assert [x["round"] for x in steps_of(st, "writing")] == [1, 2]


async def test_publishing_refuses_content_that_fails_the_final_check(monkeypatch, no_kick):
    await _ensure_agents("active")
    pid = await _new_project()
    stub(monkeypatch)
    await R.start_project(pid, None, "tester")
    st = await _to_gate2(pid)
    # A rule added after Gate 2 (e.g. the client bans a phrase): the release guard checks again.
    real = SR.rules_for
    monkeypatch.setattr(SR, "rules_for", lambda cid: {**real(cid), "forbidden_claims": ["walk daily"]})
    await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
    st = await run_until_blocked(pid)
    pub = steps_of(st, "publishing")[-1]
    assert pub["status"] == "needs_attention" and pub["result"]["status"] == "refused"
    assert "final safety check" in pub["error"] and "walk daily" in pub["error"]
    assert st["project"]["status"] == "needs_attention"


# ---------------------------------------------------------------------------
# real information: client knowledge store and source library
# ---------------------------------------------------------------------------

from backend.models.knowledge import ClientProfile, KnowledgeSource

SOURCE_TEXT = ("About 1 in 10 adults worldwide lives with diabetes. Many people with type 2 diabetes have no "
               "symptoms for years, so a simple blood sugar test is the only way to know. Common signs include "
               "feeling very thirsty, passing urine often, tiredness and blurred vision.")


async def _add_source(client_id, status, text=SOURCE_TEXT, title="Diabetes fact sheet"):
    import uuid as _uuid
    sid = f"SRC-{_uuid.uuid4().hex[:6].upper()}"
    async with async_session_maker() as s:
        s.add(KnowledgeSource(id=sid, client_id=client_id, title=title, publisher="WHO",
                              url="https://www.who.int/news-room/fact-sheets/detail/diabetes", topics=["diabetes"],
                              text=text, content_hash=_uuid.uuid4().hex[:16], status=status,
                              added_by="divya", approved_by="satya_human" if status == "approved" else None))
        await s.commit()
    return sid


async def test_client_without_an_approved_profile_stops_at_smriti(monkeypatch, no_kick):
    await _ensure_agents("active")
    seen = {}
    stub(monkeypatch, seen=seen)
    pid = await _new_project(client_id="NOPROFILE", profile=False)
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    ctx = steps_of(st, "client_context")[0]
    assert ctx["status"] == "needs_attention" and "No client profile exists for NOPROFILE" in ctx["error"]
    assert "SAM-AG-050" not in seen                                   # Shruti never ran on invented facts

    async with async_session_maker() as s:
        s.add(ClientProfile(client_id="DRAFTONLY", name="Draft Hospital", services=[], locations=[],
                            key_messages=[], status="draft", version=3, updated_by="divya"))
        await s.commit()
    pid = await _new_project(client_id="DRAFTONLY", profile=False)
    await R.start_project(pid, None, "tester")
    st = await run_until_blocked(pid)
    assert "(version 3) is not approved" in steps_of(st, "client_context")[0]["error"]


async def test_smriti_hands_the_approved_profile_to_shruti(monkeypatch, no_kick):
    await _ensure_agents("active")
    seen = {}
    stub(monkeypatch, seen=seen)
    pid = await _new_project()
    await R.start_project(pid, None, "tester")
    await run_until_blocked(pid)
    task, ctx = seen["SAM-AG-050"][0]
    pack = next(x for x in ctx["handed_over"] if x["step"] == "Client context")["record"]
    assert pack["brand_voice"] == "Calm and clear" and pack["services"] == ["Diabetes clinic"]
    assert pack["status"] == "loaded" and pack["approved_by"] == "approver"


async def test_research_is_checked_against_the_approved_library(monkeypatch, no_kick):
    await _ensure_agents("active")
    approved = await _add_source("KNOW", "approved")
    proposed = await _add_source("KNOW", "proposed", text="Diabetes screening camps run every month. " * 5,
                                 title="Unreviewed diabetes page")
    other = await _add_source("OTHER-CLIENT", "approved", text="Diabetes care at another client. " * 5,
                              title="Other client diabetes")
    facts = {"facts": [
        {"fact": "About 1 in 10 adults lives with diabetes.", "source_id": approved + "#1",
         "quote": "About 1 in 10 adults worldwide lives with diabetes."},
        {"fact": "About 1 in 5 adults lives with diabetes.", "source_id": approved,
         "quote": "About 1 in 10 adults worldwide lives with diabetes."},
        {"fact": "Screening camps run every month.", "source_id": proposed,
         "quote": "Diabetes screening camps run every month."},
        {"fact": "Cinnamon cures diabetes.", "source_id": approved, "quote": "Cinnamon fully cures diabetes in weeks."},
    ], "excluded": []}
    seen = {}
    stub(monkeypatch, seen=seen, answers={"SAM-AG-081": facts},
         writer_text=_writer(seen, "1 in 5 adults have diabetes. Get checked.", "1 in 10 adults have diabetes. Get checked."))
    pid = await _new_project(name="World Diabetes Day early signs", client_id="KNOW")
    await R.start_project(pid, "Posts about early signs of type 2 diabetes and screening.", "tester")
    st = await _to_gate2(pid)

    task, ctx = seen["SAM-AG-081"][0]
    given = {x["source_id"] for x in ctx["source_library"]}
    assert given == {approved}                         # not the unapproved one, not another client's
    assert "source_id" in task and approved in task

    res = steps_of(st, "research")[0]["result"]
    assert [f["verified"] for f in res["facts"]] == [True, False, False, False]
    assert res["facts"][0]["url"] == "https://www.who.int/news-room/fact-sheets/detail/diabetes"
    assert "figures not in the quote" in res["facts"][1]["reason"]
    assert res["facts"][2]["reason"] == "not from an approved source in the library"
    assert res["facts"][3]["reason"] == "the quote was not found in the source"
    assert res["verified_count"] == 1 and res["sources_available"] == 1

    # Shuddhi: only verified facts are evidence, so "1 in 5" goes back and "1 in 10" passes
    shuddhi = steps_of(st, "shuddhi")
    assert 'post 1: figure "1 in 5" is not in the research pack' in shuddhi[0]["result"]["code_check"]["findings"]
    assert shuddhi[1]["result"]["code_check"]["passed"] is True
    assert st["pending_approval"]["agent_id"] == "SAM-AG-052"
