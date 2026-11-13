"""Add project_steps.result_json (structured step result) — additive.

Only touches project_steps, a table added by 0001_project_tables.

Revision ID: 0002_step_result_json
Revises: 0001_project_tables
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_step_result_json"
down_revision = "0001_project_tables"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return insp.has_table(table) and any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("project_steps", "result_json"):
        with op.batch_alter_table("project_steps") as batch:
            batch.add_column(sa.Column("result_json", sa.JSON, nullable=True))


def downgrade() -> None:
    if _has_column("project_steps", "result_json"):
        with op.batch_alter_table("project_steps") as batch:
            batch.drop_column("result_json")
