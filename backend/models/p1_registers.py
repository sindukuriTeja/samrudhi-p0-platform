"""Phase 1 P1 agent registers (Daksh, Aarya, Mitra, Medha).

Daksh (SAM-AG-002): workflow_instances, work_packages, allocations, capacity_register
Aarya (SAM-AG-003): content_strategies, content_calendars, content_packages, brand_guidelines, qa_reviews
Mitra (SAM-AG-004): client_onboarding, client_communications, approval_workflows, feedback, account_health
Medha (SAM-AG-009): data_sources, kpi_governance, reports, forecasts, anomalies
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR, TEXT, TIMESTAMP, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# =============================================================================
# DAKSH (SAM-AG-002) — Delivery Orchestration Registers
# =============================================================================

class WorkflowInstance(Base):
    """Daksh's Workflow Registry — client delivery workflows."""
    __tablename__ = "workflow_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    scope_ref: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="created"
    )  # created/planning/allocated/executing/quality/approved/delivered/blocked
    stages: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    deadlines: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="P1")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_wf_client_status", "client_id", "status"),
    )


class WorkPackage(Base):
    """Daksh's Work Package Register."""
    __tablename__ = "work_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    competency_required: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    assigned_agent: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="proposed"
    )  # proposed/allocated/in_progress/done/blocked
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Allocation(Base):
    """Daksh's Allocation Register."""
    __tablename__ = "allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    allocation_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    work_package_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    competency_check: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    capacity_check: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    constraints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    decision_ref: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="active"
    )  # active/replaced/cancelled
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CapacityRegister(Base):
    """Daksh's Capacity Register — per-agent capacity."""
    __tablename__ = "capacity_register"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    throughput: Mapped[int] = mapped_column(nullable=False, default=0)
    concurrency: Mapped[int] = mapped_column(nullable=False, default=0)
    utilisation: Mapped[float] = mapped_column(nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="available"
    )  # available/busy/saturated/degraded
    measured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# =============================================================================
# AARYA (SAM-AG-003) — Creative & Content Registers
# =============================================================================

class ContentStrategy(Base):
    """Aarya's Content Strategy Register."""
    __tablename__ = "content_strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    strategy_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    pillars: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    themes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    messaging: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    audience: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="draft"
    )  # draft/approved/revised
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ContentCalendar(Base):
    """Aarya's Content Calendar Register."""
    __tablename__ = "content_calendars"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    calendar_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    period_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    items: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="draft"
    )  # draft/approved/published
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ContentPackage(Base):
    """Aarya's Content Package Register."""
    __tablename__ = "content_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    calendar_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # post/blog/video/script
    specialist: Mapped[str | None] = mapped_column(VARCHAR(30), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="proposed"
    )  # proposed/allocated/in_progress/qa/approved/done/blocked
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BrandGuidelines(Base):
    """Aarya's Brand Governance Register."""
    __tablename__ = "brand_guidelines"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    voice: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tone: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    visual_identity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    compliance_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QaReview(Base):
    """Aarya's Creative QA Register."""
    __tablename__ = "qa_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    reviewer: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    findings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    revisions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    closure_evidence: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="open"
    )  # open/resolved/rejected
    reviewed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# =============================================================================
# MITRA (SAM-AG-004) — Client Experience Registers
# =============================================================================

class ClientOnboarding(Base):
    """Mitra's Client Onboarding Register."""
    __tablename__ = "client_onboarding"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    onboarding_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    contract_ref: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    brief: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approval_workflow: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    contacts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="draft"
    )  # draft/approved/active
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ClientCommunication(Base):
    """Mitra's Client Communication Register."""
    __tablename__ = "client_communications"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    comm_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # update/approval/request/report
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="draft"
    )  # draft/approved/sent/failed
    owner: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ApprovalWorkflow(Base):
    """Mitra's Approval Workflow Register."""
    __tablename__ = "approval_workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    approval_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    item_ref: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    approver: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="pending"
    )  # pending/approved/rejected/overdue
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Feedback(Base):
    """Mitra's Feedback Register."""
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    feedback_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    category: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    routing: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    resolution: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="open"
    )  # open/routed/resolved/closed
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AccountHealth(Base):
    """Mitra's Account Health Register."""
    __tablename__ = "account_health"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    satisfaction: Mapped[float | None] = mapped_column(nullable=True)
    retention_signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    renewal_readiness: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="unknown")
    risks: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    measured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# =============================================================================
# MEDHA (SAM-AG-009) — Analytics & Intelligence Registers
# =============================================================================

class DataSource(Base):
    """Medha's Data Source Register."""
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # CRM/Ads/Analytics/Social/Finance
    connectivity: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="connected"
    )  # connected/stale/error
    freshness: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completeness: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KpiGovernance(Base):
    """Medha's KPI Governance Register."""
    __tablename__ = "kpi_governance"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kpi_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    formula: Mapped[str] = mapped_column(TEXT, nullable=False)
    version: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="1.0")
    source: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="draft"
    )  # draft/approved/deprecated
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Report(Base):
    """Medha's Report Register."""
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    client_id: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # client/management/dashboard
    content_ref: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="draft"
    )  # draft/validated/delivered/failed
    source_trace: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Forecast(Base):
    """Medha's Forecast Register."""
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)  # revenue/demand/capacity
    value: Mapped[float] = mapped_column(nullable=False)
    confidence_interval: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    accuracy: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class Anomaly(Base):
    """Medha's Anomaly Register."""
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    anomaly_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    severity: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)  # critical/major/informational
    description: Mapped[str] = mapped_column(TEXT, nullable=False)
    alert: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resolution: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    status: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, default="open"
    )  # open/acknowledged/resolved
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
