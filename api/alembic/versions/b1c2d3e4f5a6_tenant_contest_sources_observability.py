"""add tenant contest sources and contest run history

Revision ID: b1c2d3e4f5a6
Revises: a4b5c6d7e8f9
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_contest_sources",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("list_url", sa.String(1024), nullable=False),
        sa.Column("title_keywords", sa.String(512), nullable=False, server_default=""),
        sa.Column("link_selector", sa.String(512), nullable=False),
        sa.Column("content_selector", sa.String(512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("preflight_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
    )
    op.create_index("ix_tenant_contest_sources_tenant_id", "tenant_contest_sources", ["tenant_id"])
    op.create_table(
        "tenant_contest_source_items",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(255), sa.ForeignKey("tenant_contest_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", sa.String(255), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
        sa.UniqueConstraint("tenant_id", "source_id", "policy_id", name="uq_tenant_contest_source_items"),
    )
    op.create_index("ix_tenant_contest_source_items_tenant_id", "tenant_contest_source_items", ["tenant_id"])
    op.create_index("ix_tenant_contest_source_items_source_id", "tenant_contest_source_items", ["source_id"])
    op.create_table(
        "contest_runs",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("searched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feed_new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_contest_runs_tenant_target", "contest_runs", ["tenant_id", "kind", "target_id", "started_at"])


def downgrade() -> None:
    op.drop_table("contest_runs")
    op.drop_table("tenant_contest_source_items")
    op.drop_table("tenant_contest_sources")
