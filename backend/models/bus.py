"""Message bus durable log model (architecture section 5).

Every event is written here FIRST (source of truth), then Redis pub/sub for live delivery.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR, TIMESTAMP, Index, func, BigInteger, JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class BusEvent(Base):
    """Append-only durable event log."""
    __tablename__ = "bus_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(VARCHAR(50), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    source_agent: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    target_agent: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # canonical_id or "all"
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    tenant_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True, index=True)
    execution_id: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    severity: Mapped[str] = mapped_column(VARCHAR(5), nullable=False, default="info")  # info|S1..S4
    trace_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)

    __table_args__ = (
        Index("idx_bus_type", "event_type"),
        Index("idx_bus_trace", "trace_id"),
        Index("idx_bus_workflow", "workflow_id"),
        Index("idx_bus_severity", "severity", postgresql_where=(severity.in_(["S1", "S2"]))),
    )
