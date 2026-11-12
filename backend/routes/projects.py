"""Project routes for the Control Room (additive).

Reads are open like /api/agents; every write needs a signed-in human (JWT).
Approval decisions can only be written here, by a signed-in human.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.core.auth import get_current_user
from backend.core.message_bus import bus
from backend.database import async_session_maker
from backend.models.projects import Project
from backend.projects import queries
from backend.projects import runner as R
from backend.projects.common import new_project_id
from backend.projects.events import BUS_CHANNEL, UI_CHANNEL, notify, redis_alive
from backend.projects.flow import default_flow_key
from config.settings import get_settings

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _err(e: R.ProjectError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.detail)


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=200)
    rerun_of: str | None = None


class StartRequest(BaseModel):
    message: str | None = Field(default=None, max_length=10000)


class MessageRequest(BaseModel):
    text: str = Field(..., max_length=10000)


class DecisionRequest(BaseModel):
    decision: str  # approve | reject | approve_with_changes
    note: str | None = Field(default=None, max_length=10000)


@router.get("")
async def projects_list(status: str | None = None):
    """List projects, newest first. status: comma-separated filter."""
    statuses = [x.strip() for x in status.split(",") if x.strip()] if status else None
    return await queries.list_projects(statuses)


@router.post("", status_code=201)
async def projects_create(req: ProjectCreate, user: dict = Depends(get_current_user)):
    name = " ".join(req.name.split())
    if not name:
        raise HTTPException(status_code=400, detail="Give the project a name.")
    pid = new_project_id()
    async with async_session_maker() as s:
        s.add(Project(id=pid, name=name, client_id=get_settings().default_tenant_id,
                      flow_key=default_flow_key(), status="draft", created_by=user["username"],
                      rerun_of=req.rerun_of))
        await s.commit()
    await notify("project", pid)
    return (await queries.project_state(pid))["project"]


@router.get("/flow")
async def projects_flow():
    """The flow a new project runs, and whether every agent it needs is Active."""
    return await R.readiness()


@router.get("/history")
async def projects_history(q: str | None = None):
    return await queries.history(q)


@router.get("/{pid}")
async def project_detail(pid: str):
    """Full state: project, steps, conversation, approvals, counts."""
    try:
        return await queries.project_state(pid)
    except R.ProjectError as e:
        raise _err(e)


@router.get("/{pid}/steps")
async def project_steps(pid: str):
    try:
        return (await queries.project_state(pid))["steps"]
    except R.ProjectError as e:
        raise _err(e)


@router.get("/{pid}/messages")
async def project_messages(pid: str):
    try:
        return (await queries.project_state(pid))["messages"]
    except R.ProjectError as e:
        raise _err(e)


@router.get("/{pid}/summary")
async def project_summary(pid: str):
    try:
        return await queries.summary(pid)
    except R.ProjectError as e:
        raise _err(e)


@router.post("/{pid}/start")
async def project_start(pid: str, req: StartRequest | None = None, user: dict = Depends(get_current_user)):
    try:
        await R.start_project(pid, req.message if req else None, user["username"])
    except R.ProjectError as e:
        raise _err(e)
    return await queries.project_state(pid)


@router.post("/{pid}/messages", status_code=201)
async def project_message(pid: str, req: MessageRequest, user: dict = Depends(get_current_user)):
    try:
        await R.add_message(pid, req.text, user["username"])
    except R.ProjectError as e:
        raise _err(e)
    return {"ok": True}


@router.post("/{pid}/pause")
async def project_pause(pid: str, user: dict = Depends(get_current_user)):
    try:
        await R.set_paused(pid, True, user["username"])
    except R.ProjectError as e:
        raise _err(e)
    return {"ok": True}


@router.post("/{pid}/resume")
async def project_resume(pid: str, user: dict = Depends(get_current_user)):
    try:
        await R.set_paused(pid, False, user["username"])
    except R.ProjectError as e:
        raise _err(e)
    return {"ok": True}


@router.post("/{pid}/stop")
async def project_stop(pid: str, user: dict = Depends(get_current_user)):
    try:
        await R.stop_project(pid, user["username"])
    except R.ProjectError as e:
        raise _err(e)
    return {"ok": True}


@router.post("/{pid}/steps/{step_id}/retry")
async def project_retry(pid: str, step_id: int, user: dict = Depends(get_current_user)):
    try:
        await R.retry_step(pid, step_id, user["username"])
    except R.ProjectError as e:
        raise _err(e)
    return {"ok": True}


@router.post("/{pid}/approvals/{request_id}/decision")
async def project_decision(pid: str, request_id: str, req: DecisionRequest,
                           user: dict = Depends(get_current_user)):
    """Record a human decision once: approve, reject, or approve_with_changes (+ note)."""
    try:
        return await R.decide(pid, request_id, req.decision, req.note, user["username"])
    except R.ProjectError as e:
        raise _err(e)


@router.get("/{pid}/stream")
async def project_stream(pid: str, request: Request):
    """Server-sent events: 'update' whenever this project changes (Redis pub/sub)."""
    def _match(channel: str, data: dict) -> bool:
        return channel == UI_CHANNEL and data.get("project_id") == pid
    return await sse(request, _match)


async def sse(request: Request, match) -> StreamingResponse | JSONResponse:
    r = bus._redis
    if r is None or not await redis_alive():
        return JSONResponse(status_code=503, content={"detail": "Live updates offline (Redis is not reachable)."})

    async def gen():
        ps = r.pubsub()
        await ps.subscribe(UI_CHANNEL, BUS_CHANNEL)
        try:
            yield "retry: 5000\nevent: ready\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                msg = await ps.get_message(ignore_subscribe_messages=True, timeout=15)
                if msg is None:
                    yield ": keep-alive\n\n"
                    continue
                raw = msg.get("data")
                try:
                    data = json.loads(raw) if isinstance(raw, str) else {}
                except Exception:
                    data = {}
                if match(msg.get("channel"), data):
                    yield f"event: update\ndata: {json.dumps(data)}\n\n"
        finally:
            try:
                await ps.unsubscribe()
                await ps.aclose()
            except Exception:
                pass

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
