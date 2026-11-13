"""Live UI notifications over the same Redis pub/sub the message bus uses.

The database is always the source of truth; these notifications only tell
open browser tabs to re-read state. If Redis is down, nothing is lost: the UI
falls back to polling.
"""
import asyncio
import json

from backend.core.message_bus import bus
from backend.projects.common import iso, utcnow

UI_CHANNEL = "ui:events"
BUS_CHANNEL = "bus:all"  # agents' own live bus events


async def notify(kind: str, project_id: str | None = None) -> None:
    r = bus._redis
    if r is None:
        return
    try:
        await r.publish(UI_CHANNEL, json.dumps({"kind": kind, "project_id": project_id, "at": iso(utcnow())}))
    except Exception:
        pass


async def redis_alive() -> bool:
    r = bus._redis
    if r is None:
        return False
    try:
        return bool(await asyncio.wait_for(r.ping(), timeout=2))
    except Exception:
        return False
