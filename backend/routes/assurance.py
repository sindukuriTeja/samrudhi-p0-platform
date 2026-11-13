"""Assurance API: competency tests, certification and project telemetry (additive).

Reading is open like the rest of the Control Room. Running tests needs a signed-in founder or
assurance lead; certifying or revoking needs an assurance lead (backend/core/certification.py).
Activation still goes only through the existing activation gate, which now requires a valid
certification.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core import certification as C
from backend.core.auth import get_current_user
from backend.database import async_session_maker
from backend.models import Agent
from backend.models.competency import CompetencyRun
from backend.projects import certification as T
from backend.projects.flow import get_flow, required_agents

router = APIRouter(prefix="/api/assurance", tags=["assurance"])


def _can_test(user: dict) -> None:
    if user.get("role") not in C.TEST_ROLES:
        raise HTTPException(status_code=403, detail=f"Your role ({user.get('role')}) may not run competency tests.")


def _cert_out(c) -> dict:
    cond = (c.conditions or [{}])[0] if c.conditions else {}
    return {"cert_id": c.cert_id, "level": c.level, "scope": c.scope, "human_confirmed": c.human_confirmed,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None, **cond}


async def _row(s, a: Agent) -> dict:
    ev = await C.evidence(s, a.canonical_id)
    v = await C.validity(s, a.canonical_id)
    code = await C.latest_run(s, a.canonical_id, "code")
    model = await C.latest_run(s, a.canonical_id, "model")
    return {"canonical_id": a.canonical_id, "name": a.name, "designation": a.designation, "status": a.status,
            "required_level": ev["required_level"], "needs_model_test": ev["needs_model_test"],
            "code_test": T.run_out(code) if code else None, "model_test": T.run_out(model) if model else None,
            "evidence": ev, "certification": v, "ready_to_certify": ev["ready"] and not v["valid"]}


@router.get("/agents")
async def agents(scope: str = "flow"):
    """Every agent in the project chain (scope=flow) or all agents (scope=all), with evidence and certification."""
    wanted = set(required_agents(get_flow())) if scope == "flow" else None
    async with async_session_maker() as s:
        rows = (await s.execute(select(Agent).order_by(Agent.canonical_id))).scalars().all()
        out = [await _row(s, a) for a in rows if wanted is None or a.canonical_id in wanted]
    return {"agents": out, "job": T.job_state(),
            "summary": {"agents": len(out), "certified": sum(1 for r in out if r["certification"]["valid"]),
                        "ready_to_certify": sum(1 for r in out if r["ready_to_certify"])}}


@router.get("/agents/{cid}")
async def agent_detail(cid: str):
    from backend.models.assurance import Certification
    async with async_session_maker() as s:
        a = (await s.execute(select(Agent).where(Agent.canonical_id == cid))).scalars().first()
        if a is None:
            raise HTTPException(status_code=404, detail="No such agent.")
        runs = (await s.execute(select(CompetencyRun).where(CompetencyRun.agent_id == cid)
                                .order_by(CompetencyRun.id.desc()).limit(20))).scalars().all()
        certs = (await s.execute(select(Certification).where(Certification.agent_id == cid))).scalars().all()
        return {**(await _row(s, a)), "runs": [T.run_out(r) for r in runs],
                "certifications": sorted([_cert_out(c) for c in certs], key=lambda x: x["created_at"] or "", reverse=True)}


@router.post("/agents/{cid}/code-tests")
async def code_tests(cid: str, user: dict = Depends(get_current_user)):
    _can_test(user)
    return await T.run_code(cid, user["username"])


class Batch(BaseModel):
    agents: list[str] | None = Field(None, description="defaults to every agent in the project chain")


@router.post("/code-tests")
async def code_tests_all(req: Batch | None = None, user: dict = Depends(get_current_user)):
    _can_test(user)
    ids = (req.agents if req and req.agents else required_agents(get_flow()))
    results = [await T.run_code(cid, user["username"]) for cid in ids]
    return {"runs": len(results), "passed": sum(1 for r in results if r["passed"]),
            "failed": [{"agent_id": r["agent_id"], "run_id": r["run_id"]} for r in results if not r["passed"]]}


@router.post("/model-tests")
async def model_tests(req: Batch | None = None, user: dict = Depends(get_current_user)):
    """Start model competency tests in the background (one agent at a time)."""
    _can_test(user)
    ids = (req.agents if req and req.agents else required_agents(get_flow()))
    return T.start_model_job(ids, user["username"])


@router.get("/model-tests")
async def model_tests_state():
    return T.job_state()


@router.post("/agents/{cid}/certify")
async def certify(cid: str, user: dict = Depends(get_current_user)):
    async with async_session_maker() as s:
        try:
            cert = await C.certify(s, cid, user)
        except C.CertificationError as e:
            raise HTTPException(status_code=403 if "Only an assurance lead" in str(e) else 409, detail=str(e))
        return {"certification": _cert_out(cert), "validity": await C.validity(s, cid)}


class RevokeIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/agents/{cid}/revoke")
async def revoke(cid: str, req: RevokeIn, user: dict = Depends(get_current_user)):
    async with async_session_maker() as s:
        try:
            cert = await C.revoke(s, cid, user, req.reason)
        except C.CertificationError as e:
            raise HTTPException(status_code=403, detail=str(e))
        return {"certification": _cert_out(cert), "validity": await C.validity(s, cid)}


@router.get("/projects/{pid}/metrics")
async def project_metrics(pid: str):
    """Telemetry, cost and KPIs of one project, measured in code from its records."""
    from backend.core import costing
    from backend.projects.metrics import project_metrics as measure
    async with async_session_maker() as s:
        m = await measure(s, pid)
    if not m:
        raise HTTPException(status_code=404, detail="No such project.")
    return {"metrics": m, "cost": costing.cost(m), "kpis": costing.evaluate(m)}
