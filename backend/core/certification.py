"""Agent certification rules, in code.

PDF rule: agents start Proposed (C0, unverified); the assurance team certifies competency before
activation. Here:

  evidence     competency_runs rows: a passing "code" run for every agent, plus a passing "model"
               run for thinking agents that have model steps in the project chain. Evidence counts
               only if it is recent (EVIDENCE_DAYS) and was produced on the agent's CURRENT code.
  certify      a signed-in human with an assurance role (config CERTIFY_ROLES) confirms the
               evidence; a row is added to `certifications` (level C1 code-only, C2 with model
               evidence), valid for CERT_DAYS and tied to the code fingerprint.
  revoke       adds a C0 "revoked" row; the latest row decides.
  valid        the activation gate accepts an agent only with a valid certification: human
               confirmed, not expired, not revoked, at the required level, same code.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.core.competency import code_hash
from backend.models.assurance import Certification
from backend.models.competency import CompetencyRun

EVIDENCE_DAYS = 30
CERT_DAYS = 90
CERTIFY_ROLES = ("assurance_lead",)
TEST_ROLES = ("assurance_lead", "founder")


def _aware(d):
    return None if d is None else (d if d.tzinfo else d.replace(tzinfo=timezone.utc))


def model_steps_for(canonical_id: str) -> list[dict]:
    """The agent's model (think) steps in the project chain."""
    from backend.projects.flow import get_flow
    return [d for d in get_flow()["steps"] if d.get("agent") == canonical_id and d.get("mode", "think") == "think"
            and d.get("output")]


def required_level(canonical_id: str) -> str:
    return "C2" if model_steps_for(canonical_id) else "C1"


async def latest_run(s, canonical_id: str, kind: str) -> CompetencyRun | None:
    return (await s.execute(select(CompetencyRun).where(
        CompetencyRun.agent_id == canonical_id, CompetencyRun.kind == kind, CompetencyRun.status == "done")
        .order_by(CompetencyRun.id.desc()).limit(1))).scalars().first()


def _fresh(run: CompetencyRun | None, current_hash: str | None) -> tuple[bool, str]:
    if run is None:
        return False, "not tested"
    if not run.passed:
        return False, f"last test failed ({run.run_id})"
    if run.code_hash != current_hash:
        return False, "the agent's code changed since the test"
    ended = _aware(run.ended_at) or _aware(run.started_at)
    if ended and ended < datetime.now(timezone.utc) - timedelta(days=EVIDENCE_DAYS):
        return False, f"the test is older than {EVIDENCE_DAYS} days"
    return True, run.run_id


async def evidence(s, canonical_id: str) -> dict:
    h = code_hash(canonical_id)
    need_model = bool(model_steps_for(canonical_id))
    code_ok, code_ref = _fresh(await latest_run(s, canonical_id, "code"), h)
    if need_model:
        model_ok, model_ref = _fresh(await latest_run(s, canonical_id, "model"), h)
    else:
        model_ok, model_ref = True, "not needed (no model steps in the project chain)"
    return {"code_hash": h, "required_level": "C2" if need_model else "C1", "needs_model_test": need_model,
            "code": {"ok": code_ok, "ref": code_ref}, "model": {"ok": model_ok, "ref": model_ref},
            "ready": code_ok and model_ok}


async def latest_certification(s, canonical_id: str) -> Certification | None:
    rows = (await s.execute(select(Certification).where(Certification.agent_id == canonical_id))).scalars().all()
    rows.sort(key=lambda c: (_aware(c.created_at) or datetime.min.replace(tzinfo=timezone.utc), c.cert_id))
    return rows[-1] if rows else None


def _cond(cert: Certification) -> dict:
    return (cert.conditions or [{}])[0] if cert.conditions else {}


async def validity(s, canonical_id: str) -> dict:
    """Is the agent's certification valid right now? {valid, reason, level, certified_by, expires_at}."""
    cert = await latest_certification(s, canonical_id)
    if cert is None:
        return {"valid": False, "reason": "not certified (C0, unverified)", "level": "C0"}
    c = _cond(cert)
    base = {"level": cert.level, "cert_id": cert.cert_id, "certified_by": c.get("certified_by"),
            "certified_at": c.get("certified_at"), "expires_at": _aware(cert.expires_at).isoformat() if cert.expires_at else None}
    if cert.level == "C0" or cert.scope == "revoked":
        return {**base, "valid": False, "reason": f"revoked by {c.get('revoked_by')}: {c.get('reason')}"}
    if not cert.human_confirmed:
        return {**base, "valid": False, "reason": "not confirmed by a person"}
    if cert.expires_at and _aware(cert.expires_at) < datetime.now(timezone.utc):
        return {**base, "valid": False, "reason": "the certification has expired"}
    if c.get("code_hash") != code_hash(canonical_id):
        return {**base, "valid": False, "reason": "the agent's code changed after certification; test and certify again"}
    if cert.level < required_level(canonical_id):
        return {**base, "valid": False, "reason": f"{cert.level} is below the required {required_level(canonical_id)}"}
    return {**base, "valid": True, "reason": f"{cert.level} certified by {c.get('certified_by')}"}


class CertificationError(Exception):
    pass


async def certify(s, canonical_id: str, user: dict) -> Certification:
    if user.get("role") not in CERTIFY_ROLES:
        raise CertificationError(f"Only an assurance lead can certify (your role: {user.get('role')}).")
    ev = await evidence(s, canonical_id)
    if not ev["ready"]:
        missing = []
        if not ev["code"]["ok"]:
            missing.append(f"code tests: {ev['code']['ref']}")
        if not ev["model"]["ok"]:
            missing.append(f"model tests: {ev['model']['ref']}")
        raise CertificationError("The evidence is not complete: " + "; ".join(missing))
    now = datetime.now(timezone.utc)
    level = ev["required_level"]
    steps = [d["tag"] for d in model_steps_for(canonical_id)]
    cert = Certification(
        cert_id=f"CRT-{uuid.uuid4().hex[:8].upper()}", agent_id=canonical_id,
        scope=("project chain: " + ", ".join(steps)) if steps else "code tools and governance",
        level=level, human_confirmed=True, expires_at=now + timedelta(days=CERT_DAYS), created_at=now,
        conditions=[{"code_hash": ev["code_hash"], "code_run": ev["code"]["ref"], "model_run": ev["model"]["ref"],
                     "certified_by": user["username"], "certified_at": now.isoformat()}],
    )
    s.add(cert)
    await s.commit()
    return cert


async def revoke(s, canonical_id: str, user: dict, reason: str) -> Certification:
    if user.get("role") not in CERTIFY_ROLES:
        raise CertificationError(f"Only an assurance lead can revoke a certification (your role: {user.get('role')}).")
    now = datetime.now(timezone.utc)
    cert = Certification(cert_id=f"CRT-{uuid.uuid4().hex[:8].upper()}", agent_id=canonical_id, scope="revoked",
                         level="C0", human_confirmed=True, expires_at=None, created_at=now,
                         conditions=[{"revoked_by": user["username"], "reason": reason, "revoked_at": now.isoformat()}])
    s.add(cert)
    await s.commit()
    return cert
