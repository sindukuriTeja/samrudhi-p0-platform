"""Central configuration for the Samrudhi Agentic OS P0 platform.

All settings come from environment variables (via .env). No cloud services.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60

    # --- Ollama (local LLM) ---
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "samrudhi"
    postgres_user: str = "samrudhi_app"
    postgres_password: str = "change-me"

    @property
    def database_url(self) -> str:
        # Allow override via DATABASE_URL env var (used by tests with SQLite)
        import os
        env_url = os.environ.get("DATABASE_URL")
        if env_url:
            return env_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Tenant ---
    default_tenant_id: str = "DEMO-HEALTHCARE-01"

    # --- Authority ---
    authority_matrix_path: str = "config/authority_matrices"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
