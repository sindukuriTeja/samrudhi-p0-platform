"""Add project tables and approval_decisions (additive only).

Creates: projects, project_messages, project_steps, approval_decisions.
Does not touch any existing table. Each table is created only if missing, so
the migration is safe on a database where the app already created it.

Revision ID: 0001_project_tables
Revises:
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_project_tables"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.TIMESTAMP(timezone=True)


def _missing(name: str) -> bool:
    return not sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _missing("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.VARCHAR(20), primary_key=True),
            sa.Column("name", sa.VARCHAR(200), nullable=False),
            sa.Column("client_id", sa.VARCHAR(50), nullable=False),
            sa.Column("flow_key", sa.VARCHAR(50), nullable=False),
            sa.Column("status", sa.VARCHAR(20), nullable=False),
            sa.Column("created_by", sa.VARCHAR(100), nullable=False),
            sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", TS, nullable=True),
            sa.Column("ended_at", TS, nullable=True),
            sa.Column("rerun_of", sa.VARCHAR(20), nullable=True),
        )
        op.create_index("ix_projects_client_id", "projects", ["client_id"])
        op.create_index("ix_projects_status", "projects", ["status"])

    if _missing("project_messages"):
        op.create_table(
            "project_messages",
            sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.VARCHAR(20), nullable=False),
            sa.Column("author_type", sa.VARCHAR(10), nullable=False),
            sa.Column("author", sa.VARCHAR(100), nullable=True),
            sa.Column("agent_id", sa.VARCHAR(20), nullable=True),
            sa.Column("step_id", sa.INTEGER, nullable=True),
            sa.Column("kind", sa.VARCHAR(30), nullable=False),
            sa.Column("text", sa.TEXT, nullable=False),
            sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_project_messages_project_id", "project_messages", ["project_id"])
        op.create_index("idx_pmsg_project_created", "project_messages", ["project_id", "created_at"])

    if _missing("project_steps"):
        op.create_table(
            "project_steps",
            sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.VARCHAR(20), nullable=False),
            sa.Column("seq", sa.INTEGER, nullable=False),
            sa.Column("step_key", sa.VARCHAR(50), nullable=False),
            sa.Column("agent_id", sa.VARCHAR(20), nullable=False),
            sa.Column("responsibility", sa.VARCHAR(200), nullable=False),
            sa.Column("tag", sa.VARCHAR(60), nullable=False),
            sa.Column("round", sa.INTEGER, nullable=False),
            sa.Column("status", sa.VARCHAR(20), nullable=False),
            sa.Column("started_at", TS, nullable=True),
            sa.Column("ended_at", TS, nullable=True),
            sa.Column("summary", sa.TEXT, nullable=True),
            sa.Column("execution_id", sa.VARCHAR(50), nullable=True),
            sa.Column("error", sa.TEXT, nullable=True),
            sa.Column("approval_id", sa.VARCHAR(20), nullable=True),
            sa.Column("source_approval_id", sa.VARCHAR(20), nullable=True),
            sa.Column("dispatch_ref", sa.VARCHAR(80), nullable=True),
        )
        op.create_index("ix_project_steps_project_id", "project_steps", ["project_id"])
        op.create_index("ix_project_steps_agent_id", "project_steps", ["agent_id"])
        op.create_index("ix_project_steps_status", "project_steps", ["status"])
        op.create_index("idx_pstep_project_seq", "project_steps", ["project_id", "seq"])

    if _missing("approval_decisions"):
        op.create_table(
            "approval_decisions",
            sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
            sa.Column("request_id", sa.VARCHAR(20), nullable=False),
            sa.Column("project_id", sa.VARCHAR(20), nullable=True),
            sa.Column("decision", sa.VARCHAR(30), nullable=False),
            sa.Column("note", sa.TEXT, nullable=True),
            sa.Column("decided_by", sa.VARCHAR(100), nullable=False),
            sa.Column("decided_at", TS, nullable=False, server_default=sa.func.now()),
            sa.Column("details", sa.JSON, nullable=False),
        )
        op.create_index("ix_approval_decisions_request_id", "approval_decisions", ["request_id"], unique=True)
        op.create_index("ix_approval_decisions_project_id", "approval_decisions", ["project_id"])


def downgrade() -> None:
    # Drops only the tables this migration added.
    for name in ("approval_decisions", "project_steps", "project_messages", "projects"):
        if not _missing(name):
            op.drop_table(name)
