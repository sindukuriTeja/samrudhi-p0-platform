"""Tests for the Control Room project flow (additive).

The runner's dispatch is replaced with a stub so no model or worker is needed;
everything else (readiness, start, decisions, rounds, workforce counts) runs
against the SQLite test database.
"""
import pytest
from sqlalchemy import delete, select

from backend.models import Agent, Approval
from backend.models.projects import ApprovalDecision, Project, ProjectMessage, ProjectStep  # registers tables
from backend.projects import runner as R
from backend.projects import queries as Q
from backend.projects.flow import get_flow, required_agents
from backend.projects.readable import one_line, readable
from backend.database import async_session_maker


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


def test_readable_only_code():
    assert readable("```js\nconsole.log(1)\n```") == "The agent returned only code, which is not shown here."


def test_one_line_prefers_a_sentence_over_a_heading():
    assert one_line("Client Brief Capture\n\nThe brand tone is calm and reassuring. More.") == \
        "The brand tone is calm and reassuring."


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

FLOW_AGENTS = required_agents(get_flow())


async def _ensure_agents(status: str) -> None:
    async with async_session_maker() as s:
        existing = {a.canonical_id: a for a in (await s.execute(
            select(Agent).where(Agent.canonical_id.in_(FLOW_AGENTS)))).scalars().all()}
        for cid in FLOW_AGENTS:
            a = existing.get(cid)
            if a is None:
                s.add(Agent(canonical_id=cid, name=cid, designation="Test agent", position_id="POS-T",
                            department="Content", department_code="CONT", stage="P1-P2",
                            human_owner="test", technical_custodian="test", evaluator="test",
                            autonomy="bounded", priority="P1", agent_type="thinking",
                            target_competency="C3", status=status))
            else:
                a.status = status
        await s.commit()


async def _new_project(name="Test project") -> str:
    from backend.projects.common import new_project_id
    pid = new_project_id()
    async with async_session_maker() as s:
        s.add(Project(id=pid, name=name, client_id="TEST", flow_key="content_production",
                      status="draft", created_by="tester"))
        await s.commit()
    return pid


@pytest.fixture
def no_dispatch(monkeypatch):
    """Never start real agent runs in these tests."""
    monkeypatch.setattr(R.runner, "kick", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# start rules
# ---------------------------------------------------------------------------

async def test_start_refused_when_agents_not_active(no_dispatch):
    await _ensure_agents("proposed")
    pid = await _new_project()
    with pytest.raises(R.ProjectError) as e:
        await R.start_project(pid, "go", "tester")
    assert e.value.status == 409
    assert {a["canonical_id"] for a in e.value.detail["not_active"]} == set(FLOW_AGENTS)
    async with async_session_maker() as s:
        assert (await s.get(Project, pid)).status == "draft"


async def test_start_creates_steps_once(no_dispatch):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, "Make 3 posts", "tester")
    with pytest.raises(R.ProjectError):
        await R.start_project(pid, "again", "tester")  # double click is refused
    st = await Q.project_state(pid)
    assert st["project"]["status"] == "running"
    assert [x["step_key"] for x in st["steps"]] == [d["key"] for d in get_flow()["steps"]]
    assert st["messages"][0]["author_type"] == "human" and st["messages"][0]["text"] == "Make 3 posts"


async def test_runner_refuses_inactive_agent(monkeypatch):
    await _ensure_agents("active")
    monkeypatch.setattr(R.runner, "kick", lambda *a, **k: None)
    pid = await _new_project()
    await R.start_project(pid, None, "tester")
    async with async_session_maker() as s:
        first = (await s.execute(select(Agent).where(Agent.canonical_id == FLOW_AGENTS[0]))).scalars().first()
        first.status = "restricted"
        await s.commit()

    async def boom(*a, **k):
        raise AssertionError("an inactive agent must not be dispatched")
    monkeypatch.setattr(R.dispatcher, "dispatch", boom)
    assert await R.runner._advance(pid) is False
    st = await Q.project_state(pid)
    assert st["project"]["status"] == "needs_attention"
    assert st["steps"][0]["status"] == "needs_attention" and "not Active" in st["steps"][0]["error"]
    await _ensure_agents("active")


# ---------------------------------------------------------------------------
# full pass with a stubbed dispatch: approvals, rounds, decisions
# ---------------------------------------------------------------------------

async def _run_until_blocked(pid, monkeypatch, outputs):
    async def fake_dispatch(args, kwargs, on_ref):
        await on_ref("test")
        agent = args[0]
        text = outputs.get(agent, f"{agent} did the work. It is described in plain words here.")
        return {"status": "completed", "execution_id": f"exec-test-{agent}", "output": text}
    monkeypatch.setattr(R.dispatcher, "dispatch", fake_dispatch)
    while await R.runner._advance(pid):
        pass


async def test_approval_flow_with_changes_creates_new_rounds(monkeypatch, no_dispatch):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, None, "tester")
    await _run_until_blocked(pid, monkeypatch, {"SAM-AG-049": '{"tone": "calm"}'})
    st = await Q.project_state(pid)
    pending = st["pending_approval"]
    assert pending is not None and pending["agent_id"] == "SAM-AG-080"
    assert "{" not in st["messages"][1]["text"]  # JSON was turned into readable text

    # sidebar: the asking agent is counted as awaiting approval, counts add up
    wf = await Q.workforce()
    c = wf["counts"]
    assert c["active"] + c["awaiting_approval"] + c["on_standby"] + c["not_deployed"] == wf["total"]
    assert next(a for a in wf["agents"] if a["canonical_id"] == "SAM-AG-080")["state"] == "awaiting_approval"

    with pytest.raises(R.ProjectError):
        await R.decide(pid, pending["request_id"], "approve_with_changes", "  ", "tester")  # note required
    await R.decide(pid, pending["request_id"], "approve_with_changes", "Remove the word naturally.", "tester")
    with pytest.raises(R.ProjectError) as again:
        await R.decide(pid, pending["request_id"], "approve", None, "tester")  # recorded once
    assert again.value.status == 409

    st = await Q.project_state(pid)
    keys = [(x["step_key"], x["round"], x["status"]) for x in st["steps"]]
    i = keys.index(("compliance", 1, "completed"))
    assert keys[i + 1][:2] == ("writing", 2) and keys[i + 2][:2] == ("compliance", 2)
    assert ("writing", 1, "completed") in keys  # earlier round kept
    async with async_session_maker() as s:
        appr = (await s.execute(select(Approval).where(Approval.request_id == pending["request_id"]))).scalars().first()
        dec = (await s.execute(select(ApprovalDecision).where(
            ApprovalDecision.request_id == pending["request_id"]))).scalars().first()
    assert appr.decision == "approve" and appr.decided_by == "tester"
    assert dec.decision == "approve_with_changes" and dec.note == "Remove the word naturally."

    # the revision round receives the human note
    seen = {}

    async def capture(args, kwargs, on_ref):
        await on_ref("test")
        seen.setdefault(args[0], (args[1], kwargs["context"]))
        return {"status": "completed", "execution_id": "exec-x", "output": "Rewrote the captions as asked."}
    monkeypatch.setattr(R.dispatcher, "dispatch", capture)
    while await R.runner._advance(pid):
        pass
    task_text, ctx = seen["SAM-AG-082"]
    assert "Remove the word naturally." in task_text and ctx["revision_note"] == "Remove the word naturally."


async def test_reject_then_retry_and_finish(monkeypatch, no_dispatch):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, None, "tester")
    await _run_until_blocked(pid, monkeypatch, {})
    pending = (await Q.project_state(pid))["pending_approval"]
    await R.decide(pid, pending["request_id"], "reject", "Claim cannot be supported.", "tester")
    st = await Q.project_state(pid)
    assert st["project"]["status"] == "needs_attention"
    rejected = next(x for x in st["steps"] if x["approval_id"] == pending["request_id"])
    assert rejected["status"] == "needs_attention" and "Rejected by tester" in rejected["error"]

    await R.retry_step(pid, rejected["id"], "tester")
    with pytest.raises(R.ProjectError):
        await R.retry_step(pid, rejected["id"], "tester")  # retried only once
    await _run_until_blocked(pid, monkeypatch, {})
    # approve every remaining request until the project completes
    for _ in range(5):
        st = await Q.project_state(pid)
        if st["pending_approval"] is None:
            break
        await R.decide(pid, st["pending_approval"]["request_id"], "approve", None, "tester")
        await _run_until_blocked(pid, monkeypatch, {})
    st = await Q.project_state(pid)
    assert st["project"]["status"] == "completed"
    summ = await Q.summary(pid)
    assert summ["tiles"]["human_approvals"] >= 3
    assert {d["name"] for d in summ["deliverables"]} == {"Copy", "Design brief", "Review report"}
    assert any(h["id"] == pid for h in await Q.history())


async def test_model_unavailable_is_reported_not_invented(monkeypatch, no_dispatch):
    await _ensure_agents("active")
    pid = await _new_project()
    await R.start_project(pid, None, "tester")

    async def down(args, kwargs, on_ref):
        await on_ref("test")
        return {"status": "completed", "execution_id": "exec-down",
                "output": "[MODEL UNAVAILABLE] connection refused. Smriti cannot produce output."}
    monkeypatch.setattr(R.dispatcher, "dispatch", down)
    assert await R.runner._advance(pid) is False
    st = await Q.project_state(pid)
    assert st["steps"][0]["status"] == "needs_attention"
    assert st["steps"][0]["error"].startswith("Model unavailable")
    assert not any(m["author_type"] == "agent" for m in st["messages"])
