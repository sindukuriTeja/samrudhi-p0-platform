"""Run competency tests and keep the evidence (competency_runs).

code tests   backend/core/competency.py, instant, no model.
model tests  each thinking agent gets its REAL step instructions from the project chain with a
             small fixed sample project and must return the structured answer the step needs
             (valid JSON in the step's schema, the right number of items, a pass/send-back
             verdict for checkers). It runs through the same dispatcher and worker as projects,
             so the run is logged in execution_log with its telemetry.
Batch model tests run one agent after another in the background (the model is shared).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from backend.core import competency
from backend.core.certification import model_steps_for
from backend.database import async_session_maker
from backend.models.competency import CompetencyRun
from backend.projects import dispatch as dispatcher
from backend.projects import schema

log = logging.getLogger("samrudhi.certification")
TENANT = "COMPETENCY-TEST"
SAMPLE_PROJECT = "Competency test: 2 Instagram posts for World Diabetes Day for a hospital client"
COUNT = 2

POSTS = [{"headline": "Know the early signs", "caption": "Feeling very thirsty or tired? Ask your doctor about a "
          "blood sugar test. Consult your doctor for advice about your health.", "call_to_action": "Book a sugar check"},
         {"headline": "Small steps, big change", "caption": "A daily walk and healthy food lower the risk of type 2 "
          "diabetes. Consult your doctor for advice about your health.", "call_to_action": "Join our screening camp"}]
SAMPLE_INPUTS = {
    "kickoff": {"goal": "Raise awareness of early diabetes signs", "priority": "high", "deadline": "in 2 weeks"},
    "client_expectations": {"client": "Demo Healthcare Hospital", "expectations": ["plain, calm words"],
                            "sign_off_required": ["final posts"], "approval_rules": ["client approves before publishing"]},
    "client_context": {"brand_voice": "Warm, calm and plain", "audience": "Adults 35-60",
                       "services": ["Diabetes clinic", "Screening camps"], "forbidden_claims": ["miracle", "guaranteed cure"]},
    "brief": {"objective": "Two awareness posts", "audience": "Adults 35-60", "deliverables": ["2 Instagram posts"],
              "deadline": "in 2 weeks", "limits": ["no cure claims"]},
    "creative_request": {"quality_bar": ["clear and kind"], "brand_rules": ["no fear"], "research_questions": ["early signs"]},
    "research": {"facts": [{"fact": "Symptoms of type 2 diabetes can be mild and take years to notice.", "verified": True,
                            "source_id": "SRC-SAMPLE", "quote": "Symptoms of type 2 diabetes can be mild."}]},
    "direction": {"themes": ["early signs", "healthy habits"], "tone": "warm",
                  "pieces": [{"topic": "early signs", "key_message": "get checked", "call_to_action": "book a test"},
                             {"topic": "habits", "key_message": "walk daily", "call_to_action": "join a camp"}]},
    "calendar": {"posts": [{"date": "2026-11-14", "theme": "early signs", "brief": "symptoms and testing"},
                           {"date": "2026-11-16", "theme": "habits", "brief": "walking and food"}]},
    "distribution": {"posts": [{"post": "1", "platform": "Instagram", "format": "image", "time": "10:00"},
                               {"post": "2", "platform": "Instagram", "format": "image", "time": "10:00"}]},
    "writing": {"posts": POSTS},
    "design_brief": {"briefs": [{"post": "1", "look": "soft blue", "layout": "photo + headline", "text_on_image": "Know the signs"},
                                {"post": "2", "look": "green", "layout": "illustration", "text_on_image": "Walk daily"}]},
    "artwork": {"specs": [{"post": "1", "image": "person checking sugar", "text_on_image": "Know the signs"},
                          {"post": "2", "image": "family walking", "text_on_image": "Walk daily"}]},
    "costing": {"tokens": 12000, "model_runs": 20, "accepted_deliverables": 2, "total_cost": "unavailable"},
    "kpi_status": {"status": "partly_measured", "missed": [], "not_measured": ["on_time_rate"]},
    "intelligence": {"summary": "Two posts approved and scheduled.", "figures": [{"name": "posts", "value": "2"}]},
}


def _task(d: dict) -> tuple[str, dict]:
    parts = [d.get("instruction", "").strip(), f"Project: {SAMPLE_PROJECT}."]
    shape = json.dumps(schema.example(d["output"]), ensure_ascii=False)
    parts.append("Answer with ONE JSON object in exactly this shape (same keys; lists may hold as many items as "
                 f"needed): {shape}. Write \"unavailable\" for anything you do not know.")
    if d.get("count"):
        parts.append(f"The list \"{d['count']['field']}\" must contain exactly {COUNT} items, one per post.")
    if d.get("verdict"):
        parts.append('Set "verdict" to "pass" or "send_back", and give the reasons in "reasons".')
    handed = [{"step": k, "record": SAMPLE_INPUTS[k]} for k in d.get("inputs") or [] if k in SAMPLE_INPUTS]
    ctx = {"project": SAMPLE_PROJECT, "client_id": TENANT, "step": d.get("tag"), "round": 1,
           "human_instructions": [], "handed_over": handed}
    if d["key"] in ("writing", "design_brief", "artwork"):
        ctx["work_packages"] = [{"package_id": f"WP-T{i}", "type": "social_posts", "sequence": i,
                                 "due_date": "2026-11-20"} for i in (1, 2)]
    return "\n".join(p for p in parts if p), ctx


def has_content(data) -> bool:
    """At least one real value (not empty, not "unavailable")."""
    text = schema.flatten_text(data)
    return any(x.strip() and x.strip().lower() not in ("unavailable", "<text>", "n/a") for x in text.splitlines())


def check_answer(d: dict, output: str) -> tuple[bool, str]:
    data = schema.extract_json(output)
    if data is None:
        return False, "the answer was not a JSON object"
    errs = schema.validate(data, d["output"])
    if errs:
        return False, "; ".join(errs[:4])
    if d.get("count"):
        got = len(data.get(d["count"]["field"]) or [])
        if got != COUNT:
            return False, f"{d['count']['field']} has {got} items, expected {COUNT}"
    if d.get("verdict"):
        v = str(data.get("verdict", "")).lower().replace(" ", "_").replace("-", "_")
        if v not in ("pass", "send_back", "sendback"):
            return False, f"verdict is {data.get('verdict')!r}, not pass or send_back"
    if not has_content(data):
        return False, "every field is empty or unavailable"
    return True, "structured answer accepted"


async def _new_run(cid: str, kind: str, user: str) -> str:
    rid = f"CMP-{uuid.uuid4().hex[:6].upper()}"
    async with async_session_maker() as s:
        s.add(CompetencyRun(run_id=rid, agent_id=cid, kind=kind, status="running", passed=False, cases=[],
                            code_hash=competency.code_hash(cid), run_by=user,
                            started_at=datetime.now(timezone.utc)))
        await s.commit()
    return rid


async def _finish(rid: str, *, passed: bool, cases: list, tokens: int = 0, seconds: float = 0.0,
                  status: str = "done") -> dict:
    async with async_session_maker() as s:
        r = (await s.execute(select(CompetencyRun).where(CompetencyRun.run_id == rid))).scalars().first()
        r.status, r.passed, r.cases = status, passed, cases
        r.tokens, r.model_seconds = tokens, round(seconds, 2)
        r.ended_at = datetime.now(timezone.utc)
        await s.commit()
        return run_out(r)


def run_out(r: CompetencyRun) -> dict:
    return {"run_id": r.run_id, "agent_id": r.agent_id, "kind": r.kind, "status": r.status, "passed": r.passed,
            "cases": r.cases, "code_hash": r.code_hash, "tokens": r.tokens, "model_seconds": float(r.model_seconds or 0),
            "run_by": r.run_by, "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None}


async def run_code(cid: str, user: str) -> dict:
    rid = await _new_run(cid, "code", user)
    res = await asyncio.to_thread(competency.run_code_tests, cid)
    return await _finish(rid, passed=res["passed"], cases=res["cases"])


async def run_model(cid: str, user: str) -> dict:
    steps = model_steps_for(cid)
    rid = await _new_run(cid, "model", user)
    if not steps:
        return await _finish(rid, passed=True, cases=[{"name": "no model steps", "passed": True,
                                                       "detail": "this agent has no model steps in the project chain"}])
    cases, tokens, secs = [], 0, 0.0
    for d in steps:
        task, ctx = _task(d)

        async def _ref(_):
            return None
        try:
            res = await dispatcher.dispatch([cid, task, TENANT, rid], {"action": d.get("action"), "context": ctx,
                                                                      "output_format": "json"}, _ref)
        except Exception as e:  # the worker or model could not be reached
            res = {"status": "failed", "error": f"{type(e).__name__}: {e}"}
        tel = (res or {}).get("telemetry") or {}
        tokens += int((res or {}).get("tokens_used") or 0)
        secs += float(tel.get("model_seconds") or (res or {}).get("latency_s") or 0)
        if (res or {}).get("status") != "completed":
            cases.append({"name": f"{d['tag']}: structured answer", "passed": False,
                          "detail": ((res or {}).get("error") or "the run failed")[:300]})
            continue
        ok, detail = check_answer(d, res.get("output") or "")
        cases.append({"name": f"{d['tag']}: structured answer", "passed": ok, "detail": detail})
    return await _finish(rid, passed=all(c["passed"] for c in cases), cases=cases, tokens=tokens, seconds=secs)


# ---------------------------------------------------------------------------
# background batch for model tests (one at a time: the local model is shared)
# ---------------------------------------------------------------------------

JOB: dict = {"running": False, "queue": [], "done": [], "current": None, "started_by": None, "started_at": None}


def job_state() -> dict:
    return {k: (list(v) if isinstance(v, list) else v) for k, v in JOB.items()}


async def _job_loop():
    try:
        while JOB["queue"]:
            cid = JOB["queue"].pop(0)
            JOB["current"] = cid
            try:
                r = await run_model(cid, JOB["started_by"])
                JOB["done"].append({"agent_id": cid, "run_id": r["run_id"], "passed": r["passed"]})
            except Exception as e:
                log.exception("Model competency test failed for %s", cid)
                JOB["done"].append({"agent_id": cid, "run_id": None, "passed": False, "error": str(e)[:200]})
    finally:
        JOB["running"], JOB["current"] = False, None


def start_model_job(agent_ids: list[str], user: str) -> dict:
    todo = [a for a in agent_ids if model_steps_for(a)]
    if JOB["running"]:
        JOB["queue"] += [a for a in todo if a not in JOB["queue"] and a != JOB["current"]]
        return job_state()
    JOB.update(running=True, queue=todo, done=[], current=None, started_by=user,
               started_at=datetime.now(timezone.utc).isoformat())
    asyncio.get_running_loop().create_task(_job_loop())
    return job_state()
