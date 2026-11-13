"""Knowledge API: the client knowledge store and the approved source library (additive).

Reading is open like the rest of the Control Room API. Every write needs a signed-in person with
a role listed in config/knowledge.yaml, and an approval must come from a different person than
the one who last edited the profile or added the source (four-eyes rule, checked in code).
Agents never call these endpoints and never fetch pages.
"""
import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.core import knowledge as kn
from backend.core import safety_rules
from backend.core.auth import get_current_user
from backend.database import async_session_maker
from backend.models.knowledge import ClientProfile, KnowledgeSource
from backend.projects.common import utcnow
from backend.projects.runner import profile_out
from config.settings import get_settings

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _allowed(action: str, user: dict) -> None:
    roles = (kn.config().get("roles") or {}).get(action) or []
    if user.get("role") not in roles:
        raise HTTPException(status_code=403, detail=f"Your role ({user.get('role')}) may not {action.replace('_', ' ')}.")


def _source_out(r: KnowledgeSource, full: bool = False) -> dict:
    out = {"id": r.id, "client_id": r.client_id, "title": r.title, "publisher": r.publisher, "url": r.url,
           "topics": list(r.topics or []), "origin": r.origin, "status": r.status, "added_by": r.added_by,
           "added_at": r.added_at.isoformat() if r.added_at else None,
           "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else None,
           "approved_by": r.approved_by, "approved_at": r.approved_at.isoformat() if r.approved_at else None,
           "chars": len(r.text or "")}
    out["text"] = r.text if full else (r.text or "")[:400]
    return out


def _clean_list(v) -> list[str]:
    return [" ".join(str(x).split()) for x in (v or []) if str(x).strip()][:30]


# ---------------------------------------------------------------------------
# client profiles
# ---------------------------------------------------------------------------

class ProfileIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brand_voice: str = Field("", max_length=2000)
    audience: str = Field("", max_length=2000)
    services: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    key_messages: list[str] = Field(default_factory=list)


@router.get("/clients")
async def clients_list():
    """Every client with a profile or with safety rules, and the profile's status."""
    async with async_session_maker() as s:
        rows = {r.client_id: profile_out(r) for r in (await s.execute(select(ClientProfile))).scalars().all()}
    ids = list(rows) + [c for c in (safety_rules._load().get("clients") or {}) if c not in rows]
    default = get_settings().default_tenant_id
    if default not in ids:
        ids.insert(0, default)
    return [rows.get(cid) or {"client_id": cid, "name": (safety_rules._load().get("clients") or {}).get(cid, {}).get("name") or cid,
                              "status": "missing"} for cid in ids]


@router.get("/clients/{client_id}")
async def client_get(client_id: str):
    async with async_session_maker() as s:
        cp = await s.get(ClientProfile, client_id)
    return {"profile": profile_out(cp) if cp else None, "rules": safety_rules.rules_for(client_id)}


@router.put("/clients/{client_id}")
async def client_put(client_id: str, req: ProfileIn, user: dict = Depends(get_current_user)):
    """Create or edit a profile. Any edit makes it a draft again until a second person approves it."""
    _allowed("edit_profile", user)
    async with async_session_maker() as s:
        cp = await s.get(ClientProfile, client_id)
        if cp is None:
            cp = ClientProfile(client_id=client_id, version=0, services=[], locations=[], key_messages=[],
                               updated_by=user["username"])
            s.add(cp)
        cp.name = " ".join(req.name.split())
        cp.brand_voice, cp.audience = req.brand_voice.strip(), req.audience.strip()
        cp.services, cp.locations = _clean_list(req.services), _clean_list(req.locations)
        cp.key_messages = _clean_list(req.key_messages)
        cp.status, cp.version = "draft", (cp.version or 0) + 1
        cp.updated_by, cp.updated_at = user["username"], utcnow()
        cp.approved_by = cp.approved_at = None
        await s.commit()
        await s.refresh(cp)
        return profile_out(cp)


@router.post("/clients/{client_id}/approve")
async def client_approve(client_id: str, user: dict = Depends(get_current_user)):
    _allowed("approve_profile", user)
    async with async_session_maker() as s:
        cp = await s.get(ClientProfile, client_id)
        if cp is None:
            raise HTTPException(status_code=404, detail="No profile for this client.")
        if cp.status == "approved":
            return profile_out(cp)
        if cp.updated_by == user["username"]:
            raise HTTPException(status_code=409, detail="You made the last change; a different person must approve it.")
        cp.status, cp.approved_by, cp.approved_at = "approved", user["username"], utcnow()
        await s.commit()
        await s.refresh(cp)
        return profile_out(cp)


# ---------------------------------------------------------------------------
# source library
# ---------------------------------------------------------------------------

class SourceIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    publisher: str = Field("", max_length=200)
    url: str = Field("", max_length=1000)
    topics: list[str] = Field(default_factory=list)
    text: str = Field(..., min_length=200, max_length=30000)
    client_id: str | None = Field(None, max_length=50)     # None = shared by all clients


class FetchIn(BaseModel):
    url: str = Field(..., max_length=1000)
    title: str | None = Field(None, max_length=300)
    publisher: str = Field("", max_length=200)
    topics: list[str] = Field(default_factory=list)
    client_id: str | None = Field(None, max_length=50)


async def _add_source(user: dict, *, title, publisher, url, topics, text, client_id, origin, retrieved=None) -> dict:
    h = kn.content_hash(text)
    async with async_session_maker() as s:
        dup = (await s.execute(select(KnowledgeSource).where(
            KnowledgeSource.content_hash == h, KnowledgeSource.status != "retired"))).scalars().first()
        if dup is not None:
            raise HTTPException(status_code=409, detail=f"This text is already in the library as {dup.id}.")
        row = KnowledgeSource(id=f"SRC-{uuid.uuid4().hex[:6].upper()}", client_id=client_id or None,
                              title=" ".join(title.split())[:300], publisher=publisher.strip(), url=url.strip(),
                              topics=_clean_list(topics), text=text, content_hash=h, origin=origin,
                              status="proposed", added_by=user["username"], added_at=utcnow(),
                              retrieved_at=retrieved)
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return _source_out(row)


@router.get("/sources")
async def sources_list(client_id: str | None = None, status: str | None = None):
    q = select(KnowledgeSource).order_by(KnowledgeSource.added_at.desc())
    if status:
        q = q.where(KnowledgeSource.status.in_([x.strip() for x in status.split(",") if x.strip()]))
    if client_id:
        q = q.where((KnowledgeSource.client_id == client_id) | (KnowledgeSource.client_id.is_(None)))
    async with async_session_maker() as s:
        return [_source_out(r) for r in (await s.execute(q)).scalars().all()]


@router.get("/sources/{source_id}")
async def source_get(source_id: str):
    async with async_session_maker() as s:
        r = await s.get(KnowledgeSource, source_id)
    if r is None:
        raise HTTPException(status_code=404, detail="No such source.")
    return _source_out(r, full=True)


@router.post("/sources", status_code=201)
async def source_add(req: SourceIn, user: dict = Depends(get_current_user)):
    """Add a source from pasted text (no network). It is 'proposed' until a second person approves it."""
    _allowed("add_source", user)
    if req.url and not req.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="The link must start with https://")
    return await _add_source(user, title=req.title, publisher=req.publisher, url=req.url, topics=req.topics,
                             text=req.text.strip(), client_id=req.client_id, origin="pasted")


@router.post("/sources/fetch", status_code=201)
async def source_fetch(req: FetchIn, user: dict = Depends(get_current_user)):
    """Fetch a page from an allowed https site into the library ('proposed' until approved)."""
    _allowed("add_source", user)
    try:
        page = await asyncio.to_thread(kn.fetch_page, req.url)
    except kn.FetchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"The page could not be fetched: {type(e).__name__}")
    return await _add_source(user, title=req.title or page["title"] or req.url, publisher=req.publisher,
                             url=page["final_url"], topics=req.topics, text=page["text"],
                             client_id=req.client_id, origin="fetched", retrieved=utcnow())


@router.post("/sources/{source_id}/approve")
async def source_approve(source_id: str, user: dict = Depends(get_current_user)):
    _allowed("approve_source", user)
    async with async_session_maker() as s:
        r = await s.get(KnowledgeSource, source_id)
        if r is None:
            raise HTTPException(status_code=404, detail="No such source.")
        if r.status == "retired":
            raise HTTPException(status_code=409, detail="A retired source cannot be approved; add it again.")
        if r.added_by == user["username"]:
            raise HTTPException(status_code=409, detail="You added this source; a different person must approve it.")
        r.status, r.approved_by, r.approved_at = "approved", user["username"], utcnow()
        await s.commit()
        await s.refresh(r)
        return _source_out(r)


@router.post("/sources/{source_id}/retire")
async def source_retire(source_id: str, user: dict = Depends(get_current_user)):
    """Take a source out of use (kept for the record; facts can no longer be verified against it)."""
    _allowed("approve_source", user)
    async with async_session_maker() as s:
        r = await s.get(KnowledgeSource, source_id)
        if r is None:
            raise HTTPException(status_code=404, detail="No such source.")
        r.status = "retired"
        await s.commit()
        await s.refresh(r)
        return _source_out(r)


@router.get("/search")
async def search(q: str, client_id: str | None = None):
    """Preview what Anvesh would be given for a topic (approved sources only)."""
    from backend.projects.runner import _approved_sources
    async with async_session_maker() as s:
        sources = await _approved_sources(s, client_id or get_settings().default_tenant_id)
    return kn.retrieve(q, sources)
