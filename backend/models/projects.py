"""Project tables for the Control Room project flow (additive).

New tables only — nothing here changes an existing table:
  projects            one row per project a human creates
  project_messages    the project conversation (human, agent, system)
  project_steps       one row per agent step / round, linked to execution_log
                      (execution_id) and approvals (approval_id)
  approval_decisions  append-only record of every human decision on an
                      approval, including "approve_with_changes" + note, which
                      the existing approvals.decision column (approve|reject)
                      cannot hold
"""
from datetime import datetime

from sqlalchemy import INTEGER, JSON, TEXT, TIMESTAMP, VARCHAR, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(VARCHAR(20), primary_key=True)  # PRJ-XXXXXXXX
    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    client_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    flow_key: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    # draft | running | paused | needs_attention | completed | stopped
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="draft", index=True)
    created_by: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rerun_of: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)


class ProjectMessage(Base):
    __tablename__ = "project_messages"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    author_type: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)  # human | agent | system
    author: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)  # human login
    agent_id: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    step_id: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    kind: Mapped[str] = mapped_column(VARCHAR(30), nullable=False, default="message")
    text: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_pmsg_project_created", "project_id", "created_at"),)


class ProjectStep(Base):
    __tablename__ = "project_steps"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(INTEGER, nullable=False)
    step_key: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    agent_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, index=True)
    responsibility: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    tag: Mapped[str] = mapped_column(VARCHAR(60), nullable=False)
    round: Mapped[int] = mapped_column(INTEGER, nullable=False, default=1)
    # queued | in_progress | completed | needs_attention | skipped
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    execution_id: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)  # -> execution_log
    error: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    approval_id: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)  # -> approvals.request_id
    source_approval_id: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)  # round caused by
    dispatch_ref: Mapped[str | None] = mapped_column(VARCHAR(80), nullable=True)  # celery task id / "local"
    # structured result of the step: tool output, or {"verdict": ..., "reasons": ...} for checkers
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (Index("idx_pstep_project_seq", "project_id", "seq"),)


class ApprovalDecision(Base):
    """Append-only: one row per human decision on an approvals row."""
    __tablename__ = "approval_decisions"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, unique=True, index=True)
    project_id: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True, index=True)
    decision: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)  # approve | reject | approve_with_changes
    note: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    decided_by: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
