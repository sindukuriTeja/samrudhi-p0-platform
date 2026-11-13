"""Knowledge tables: client_profiles and knowledge_sources — additive (new tables only).

Revision ID: 0003_knowledge
Revises: 0002_step_result_json
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_knowledge"
down_revision = "0002_step_result_json"
branch_labels = None
depends_on = None


def _has(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has("client_profiles"):
        op.create_table(
            "client_profiles",
            sa.Column("client_id", sa.VARCHAR(50), primary_key=True),
            sa.Column("name", sa.VARCHAR(200), nullable=False),
            sa.Column("brand_voice", sa.TEXT, nullable=False, server_default=""),
            sa.Column("audience", sa.TEXT, nullable=False, server_default=""),
            sa.Column("services", sa.JSON, nullable=False),
            sa.Column("locations", sa.JSON, nullable=False),
            sa.Column("key_messages", sa.JSON, nullable=False),
            sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="draft"),
            sa.Column("version", sa.INTEGER, nullable=False, server_default="1"),
            sa.Column("updated_by", sa.VARCHAR(100), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("approved_by", sa.VARCHAR(100), nullable=True),
            sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
    if not _has("knowledge_sources"):
        op.create_table(
            "knowledge_sources",
            sa.Column("id", sa.VARCHAR(20), primary_key=True),
            sa.Column("client_id", sa.VARCHAR(50), nullable=True),
            sa.Column("title", sa.VARCHAR(300), nullable=False),
            sa.Column("publisher", sa.VARCHAR(200), nullable=False, server_default=""),
            sa.Column("url", sa.VARCHAR(1000), nullable=False, server_default=""),
            sa.Column("topics", sa.JSON, nullable=False),
            sa.Column("text", sa.TEXT, nullable=False),
            sa.Column("content_hash", sa.VARCHAR(32), nullable=False),
            sa.Column("origin", sa.VARCHAR(20), nullable=False, server_default="pasted"),
            sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="proposed"),
            sa.Column("added_by", sa.VARCHAR(100), nullable=False),
            sa.Column("added_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("retrieved_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("approved_by", sa.VARCHAR(100), nullable=True),
            sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index("ix_knowledge_sources_client_id", "knowledge_sources", ["client_id"])
        op.create_index("ix_knowledge_sources_status", "knowledge_sources", ["status"])


def downgrade() -> None:
    if _has("knowledge_sources"):
        op.drop_table("knowledge_sources")
    if _has("client_profiles"):
        op.drop_table("client_profiles")
