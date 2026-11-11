"""Agent registry and lifecycle models (Niyantrak's domain).

Corresponds to architecture section 8.3 DDL.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    UUID, VARCHAR, INTEGER, TEXT, TIMESTAMP, ForeignKey, Index,
    BigInteger, String, Boolean, Numeric, JSON, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class LifecycleState(str, Enum):
    """8-state agent lifecycle (architecture section 9)."""
    PROPOSED = "proposed"
    REGISTERED = "registered"
    CONFIGURED = "configured"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORED = "monitored"
    RESTRICTED = "restricted"
    RETIRED = "retired"


class Agent(Base):
    """Digital Agent Master Record — holds ALL agents (P0 + P1)."""
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    designation: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    position_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    legacy_alias: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    department: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    department_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)  # P0-1A, P1-P1..
    reports_to_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True
    )
    human_owner: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    technical_custodian: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    evaluator: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    autonomy: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # bounded|full|supervised
    priority: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, index=True)  # P0|P1|P2
    agent_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # thinking|service-first|role
    target_competency: Mapped[str] = mapped_column(VARCHAR(5), nullable=False)  # C0..C5
    current_level: Mapped[str] = mapped_column(VARCHAR(5), nullable=False, default="C0")
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="proposed", index=True
    )  # LifecycleState values
    model: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, default="qwen2.5:7b")
    prompt_version: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="1.0.0")
    spec_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reports_to: Mapped["Agent | None"] = relationship(
        "Agent", remote_side=[id], foreign_keys=[reports_to_id]
    )

    __table_args__ = (
        Index("idx_agents_status", "status"),
        Index("idx_agents_department", "department_code"),
        Index("idx_agents_priority", "priority"),
        Index("idx_agents_stage", "stage"),
    )


class AgentVersion(Base):
    """Append-only: prompt/model/tool/workflow versions per agent."""
    __tablename__ = "agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    version: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    model_name: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    workflow_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class LifecycleEvent(Base):
    """Append-only: every state transition + gate results."""
    __tablename__ = "lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    to_state: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    gate_results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    performed_by: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)  # agent or human
    reason: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class AgentSpec(Base):
    """Append-only: static spec JSON per agent (from README YAML/JSON blocks)."""
    __tablename__ = "agent_specs"

    canonical_id: Mapped[str] = mapped_column(VARCHAR(20), primary_key=True)
    spec_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_readme: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
