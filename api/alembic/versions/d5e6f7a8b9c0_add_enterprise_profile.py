"""add enterprise_profiles table (per-tenant structured org profile)

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-13

企业档案：每个租户一行，承载组织级结构化信息(企业名称/地区/行业/规模/主营业务等)。
列表型字段(资质/技术域/关键词)与未来增量字段统一以 attributes(JSONB) 承载，
tenant_id 为主键兼外键(ON DELETE CASCADE)。纯新增表，向后兼容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "enterprise_profiles",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("province", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("city", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("district", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("industry", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("scale", sa.String(length=32), server_default=sa.text("'unspecified'"), nullable=False),
        sa.Column("main_business", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
            name="fk_enterprise_profiles_tenant_id",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_enterprise_profiles_tenant_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("enterprise_profiles")
