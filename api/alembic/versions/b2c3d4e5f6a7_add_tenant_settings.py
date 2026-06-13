"""add tenant_settings table (per-tenant LLM key / BYO key)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13

按租户隔离 LLM 配置(BYO key)。新增 tenant_settings 表，每个租户一行，
llm_config 以 JSONB 存储组织自定义 LLM 配置；NULL 表示该组织未覆盖，运行时
回落到平台默认配置(config.yaml)。tenant_id 为主键兼外键(ON DELETE CASCADE)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("llm_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP(0)"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP(0)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
            name="fk_tenant_settings_tenant_id",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_tenant_settings_tenant_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tenant_settings")
