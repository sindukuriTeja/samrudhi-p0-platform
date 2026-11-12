"""competency_runs (additive): evidence for certification.

One row per competency test run of one agent: kind "code" (backend/core/competency.py, no model)
or "model" (the agent answers its real step instructions; see backend/projects/certification.py).
Certifications themselves are rows in the existing `certifications` table.
"""
from datetime import datetime

from sqlalchemy import BOOLEAN, INTEGER, JSON, TIMESTAMP, VARCHAR, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class CompetencyRun(Base):
    __tablename__ = "competency_runs"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False)        # CMP-XXXXXX
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)                         # code | model
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="running")   # running | done | failed
    passed: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    cases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    code_hash: Mapped[str | None] = mapped_column(VARCHAR(32), nullable=True)
    tokens: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    model_seconds: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    run_by: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
