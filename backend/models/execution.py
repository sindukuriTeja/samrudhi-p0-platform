"""Execution telemetry model (all agents write).

Corresponds to architecture section 8.3 — execution_log table.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR, TEXT, TIMESTAMP, INTEGER, Numeric, JSON, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ExecutionLog(Base):
    """Append-only: every agent run, full structured record."""
    __tablename__ = "execution_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[str] = mapped_column(VARCHAR(50), unique=True, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)  # canonical_id
    workflow_id: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True, index=True)
    task: Mapped[str] = mapped_column(TEXT, nullable=False)
    tenant_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # running|completed|failed|escalated
    tokens_used: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    response_tokens: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    latency_s: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tools_called: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    output_ref: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    trace_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    raw_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_execution_agent", "agent_id"),
        Index("idx_execution_started", "started_at"),
        Index("idx_execution_trace", "trace_id"),
    )


class CapacityMetric(Base):
    """Append-only: tokens/runs/failures per agent per day (daily rows)."""
    __tablename__ = "capacity_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    day: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    runs: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    avg_latency_s: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
