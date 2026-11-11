"""Assurance models — Satya's domain (architecture section 8.3).

Findings, evaluations, certifications, escalations — all append-only.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR, TEXT, TIMESTAMP, Index, func, Boolean,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Finding(Base):
    """Append-only: S1–S4 findings with mandatory evidence."""
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    finding_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(VARCHAR(5), nullable=False)  # S1..S4
    category: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="open")  # open|contained|resolving|closed
    raised_by: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # evaluator canonical_id
    raised_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class Evaluation(Base):
    """Append-only: 5-dimension performance evaluations."""
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    evaluator_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # must != agent_id
    scope: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    scores: Mapped[dict] = mapped_column(JSON, nullable=False)  # {quality, efficiency, reliability, contribution, adaptability}
    overall: Mapped[float] = mapped_column(VARCHAR(10), nullable=False)
    notes: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class Certification(Base):
    """Append-only: certification records (task-specific, human-confirmed)."""
    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cert_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    level: Mapped[str] = mapped_column(VARCHAR(5), nullable=False)  # C0..C5
    human_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_cert_agent", "agent_id"),
        Index("idx_cert_confirmed", "human_confirmed", postgresql_where=(human_confirmed == True)),
    )


class Escalation(Base):
    """Append-only: escalation records."""
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    escalation_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False)
    source_agent: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    severity: Mapped[str] = mapped_column(VARCHAR(5), nullable=False)
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    escalated_to: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)  # human role
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class Incident(Base):
    """Append-only timeline + status field for incidents."""
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(VARCHAR(5), nullable=False)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="open")
    timeline: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    root_cause: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    fix: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
