"""add official source preset to tenant contest sources

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_contest_sources",
        sa.Column("preset_source_id", sa.String(255), sa.ForeignKey("contest_sources.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_contest_sources", "preset_source_id")
