"""FastAPI application — the human control room backend.

REST-only, decoupled from frontend. Startup initializes DB + Redis + bus.
"""
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.core.message_bus import bus
from backend.routes import auth, agents
from config.settings import get_settings

settings = get_settings()
_redis: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks."""
    global _redis
    # Init DB tables
    await init_db()
    # Connect Redis (optional — bus falls back to durable log if Redis down)
    try:
        _redis = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await _redis.ping()
        bus._redis = _redis
    except Exception:
        bus._redis = None
    yield
    if _redis is not None:
        await _redis.close()


app = FastAPI(
    title="Samrudhi Agentic OS — P0",
    version="0.1.0",
    description="Local agentic AI platform. All agents run on Ollama. No cloud APIs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules (after app is created)
app.include_router(auth.router)
app.include_router(agents.router)


@app.get("/api/health")
async def health():
    """Health check: DB, Redis, Ollama."""
    from backend.core.llm import check_ollama_health
    from backend.database import async_session_maker
    from sqlalchemy import text

    db_ok = False
    try:
        async with async_session_maker() as s:
            await s.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    redis_ok = bus._redis is not None
    try:
        if bus._redis is not None:
            redis_ok = await bus._redis.ping()
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down (bus uses durable log only)",
        "ollama": await check_ollama_health(),
    }
