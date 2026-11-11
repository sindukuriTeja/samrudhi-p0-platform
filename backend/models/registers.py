"""Arjun's registers + approvals (architecture section 8.3).

Initiatives, decisions, risks, actions, briefs, approvals.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR, TEXT, TIMESTAMP, Index, func, Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Initiative(Base):
    """Arjun's Enterprise Initiative Register — UPDATE on status."""
    __tablename__ = "initiatives"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    objective_ref: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    owner_agent: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    milestones: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="proposed")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Decision(Base):
    """Arjun's Decision Register — UPDATE on decision field once."""
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recommendation: Mapped[str] = mapped_column(TEXT, nullable=False)
    options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approver: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    decision: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    follow_up_action_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class Risk(Base):
    """Arjun's Risk & Escalation Register — UPDATE on status."""
    __tablename__ = "risks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    severity: Mapped[str] = mapped_column(VARCHAR(5), nullable=False)  # S1..S4
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    owner: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    containment: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="open")
    escalated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Action(Base):
    """Arjun's Cross-Department Action Tracker — UPDATE on status."""
    __tablename__ = "actions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    task: Mapped[str] = mapped_column(TEXT, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="open")
    closure_evidence: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Brief(Base):
    """Arjun's briefs — append-only."""
    __tablename__ = "briefs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brief_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # daily|weekly|monthly|quarterly
    period: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    generated_by: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # SAM-AG-001
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class Approval(Base):
    """Human approvals/decisions — append-only."""
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # role|certification|activation|suspension|other
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    requested_by: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # agent canonical_id or system
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    decision: Mapped[str | None] = mapped_column(VARCHAR(10), nullable=True)  # approve|reject (null=pending)
    decided_by: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)  # human login
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    __table_args__ = (
        Index("idx_appr_pending", "request_id", postgresql_where=(decision.is_(None))),
    )
