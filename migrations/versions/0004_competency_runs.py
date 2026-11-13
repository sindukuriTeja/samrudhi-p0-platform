"""competency_runs (evidence for agent certification) and approval_signoffs (Gate 2 parties) — additive.

Revision ID: 0004_competency_runs
Revises: 0003_knowledge
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_competency_runs"
down_revision = "0003_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("competency_runs"):
        op.create_table(
            "competency_runs",
            sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.VARCHAR(20), nullable=False, unique=True),
            sa.Column("agent_id", sa.VARCHAR(20), nullable=False),
            sa.Column("kind", sa.VARCHAR(10), nullable=False),
            sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="running"),
            sa.Column("passed", sa.BOOLEAN, nullable=False, server_default=sa.false()),
            sa.Column("cases", sa.JSON, nullable=False),
            sa.Column("code_hash", sa.VARCHAR(32), nullable=True),
            sa.Column("tokens", sa.INTEGER, nullable=False, server_default="0"),
            sa.Column("model_seconds", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("run_by", sa.VARCHAR(100), nullable=False),
            sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index("ix_competency_runs_agent_id", "competency_runs", ["agent_id"])
    if not sa.inspect(op.get_bind()).has_table("approval_signoffs"):
        op.create_table(
            "approval_signoffs",
            sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
            sa.Column("request_id", sa.VARCHAR(20), nullable=False),
            sa.Column("project_id", sa.VARCHAR(20), nullable=False),
            sa.Column("party", sa.VARCHAR(30), nullable=False),
            sa.Column("decision", sa.VARCHAR(30), nullable=False),
            sa.Column("note", sa.TEXT, nullable=True),
            sa.Column("decided_by", sa.VARCHAR(100), nullable=False),
            sa.Column("role", sa.VARCHAR(50), nullable=True),
            sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_approval_signoffs_request_id", "approval_signoffs", ["request_id"])
        op.create_index("ix_approval_signoffs_project_id", "approval_signoffs", ["project_id"])
        op.create_index("uq_signoff_request_party", "approval_signoffs", ["request_id", "party"], unique=True)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("approval_signoffs"):
        op.drop_table("approval_signoffs")
    if sa.inspect(op.get_bind()).has_table("competency_runs"):
        op.drop_table("competency_runs")
