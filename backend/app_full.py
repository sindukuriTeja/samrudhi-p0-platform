"""Full Control Room app: the existing API + project flow + web UI (additive).

Run with:  uvicorn backend.app_full:app --port 8000

- Reuses backend.main:app unchanged (same endpoints, same startup).
- Adds /api/projects/* and /api/workforce/* routes.
- Serves the new UI at /            (web/)
- Serves the previous UI at /legacy (frontend/)
- After startup: recovers project runs interrupted by a restart, and keeps
  trying to reconnect Redis for live updates if it was down at startup.
"""
import asyncio
import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.main import app
from backend.models import projects as _project_models  # noqa: F401  (registers the new tables)
from backend.models import knowledge as _knowledge_models  # noqa: F401
from backend.core.message_bus import bus
from backend.projects.runner import runner
from backend.routes import projects as projects_routes
from backend.routes import workforce as workforce_routes
from backend.routes import knowledge as knowledge_routes
from config.settings import get_settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
LEGACY_DIR = os.path.join(ROOT, "frontend")

app.include_router(projects_routes.router)
app.include_router(workforce_routes.router)
app.include_router(knowledge_routes.router)


async def _redis_reconnect_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(10)
        if bus._redis is not None:
            try:
                await bus._redis.ping()
                continue
            except Exception:
                pass
        try:
            client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await client.ping()
            bus._redis = client
        except Exception:
            pass


_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(a):
    async with _original_lifespan(a):
        await runner.recover()
        reconnect = asyncio.create_task(_redis_reconnect_loop())
        try:
            yield
        finally:
            reconnect.cancel()
            await runner.shutdown()


app.router.lifespan_context = _lifespan


@app.get("/legacy", include_in_schema=False)
async def _legacy_redirect():
    return RedirectResponse(url="/legacy/")


app.mount("/legacy/", StaticFiles(directory=LEGACY_DIR, html=True), name="legacy")
app.mount("/assets", StaticFiles(directory=os.path.join(WEB_DIR, "assets")), name="assets")


@app.get("/", include_in_schema=False)
async def _index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"), headers={"Cache-Control": "no-cache"})
