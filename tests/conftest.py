"""pytest configuration for Samrudhi P0.

Sets up env vars so config loads without a .env file during tests.
Creates an in-memory SQLite DB and all tables before async tests run.
"""
import os
import pytest
import pytest_asyncio

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./tests/test_samrudhi.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

pytest_plugins = ("pytest_asyncio",)


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _create_tables():
    """Create all tables once per test session."""
    # Force settings to re-read env vars (cache cleared by pytest import order)
    from config.settings import get_settings
    get_settings.cache_clear()
    from backend.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    get_settings.cache_clear()
