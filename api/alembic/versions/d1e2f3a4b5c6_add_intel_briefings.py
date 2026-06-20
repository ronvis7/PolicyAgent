"""add intel_briefings table (proactive intelligence briefing, latest-per-tenant)

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-20

主动情报 Agent：每租户保存最新一份"带理由的优先级机会简报"。简报正文整体存 content(JSONB)，
tenant_id 主键兼外键(ON DELETE CASCADE)。纯新增表，向后兼容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "intel_briefings",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "generated_at", sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            ondelete="CASCADE", name="fk_intel_briefings_tenant_id",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_intel_briefings_tenant_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("intel_briefings")
