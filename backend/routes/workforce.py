"""Workforce summary for the Control Room sidebar and Agents page (additive, read-only)."""
from fastapi import APIRouter, Request

from backend.projects import queries
from backend.projects.events import UI_CHANNEL, BUS_CHANNEL
from backend.routes.projects import sse

router = APIRouter(prefix="/api/workforce", tags=["workforce"])


@router.get("")
async def workforce_summary():
    """Per-agent derived state, the four sidebar counts, monitoring and system health."""
    return await queries.workforce()


@router.get("/stream")
async def workforce_stream(request: Request):
    """Server-sent events whenever any project or agent bus event happens."""
    return await sse(request, lambda channel, data: channel in (UI_CHANNEL, BUS_CHANNEL))
