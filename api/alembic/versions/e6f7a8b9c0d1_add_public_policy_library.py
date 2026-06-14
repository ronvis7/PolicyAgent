"""add public policy library (policies table + knowledge_bases.is_public + system public tenant)

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-06-14

主线②公开政策库（全局共享层）：
1. policies 全局表（非租户隔离，source_url 唯一去重）承载结构化政策；
2. knowledge_bases 增 is_public 标志，标记跨租户共享的全局公开库（向量双写目标）；
3. 播种系统租户 'public'，让公开知识库/文件/切片满足既有 tenant 外键约束（零侵入复用 RAG 流水线）。
纯新增，向后兼容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 系统公开租户：承载公开政策库的向量数据，满足 knowledge_bases/files/chunks 的 tenant 外键
_PUBLIC_TENANT_ID = "public"


def upgrade() -> None:
    """Upgrade schema."""
    # 1. policies 全局结构化政策表
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("index_number", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("title", sa.String(length=512), server_default=sa.text("''"), nullable=False),
        sa.Column("issuer", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("doc_number", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("body_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("region", sa.String(length=128), server_default=sa.text("''"), nullable=False),
        sa.Column("crawled_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_policies_id"),
        sa.UniqueConstraint("source_url", name="uq_policies_source_url"),
    )
    op.create_index("ix_policies_source_url", "policies", ["source_url"])
    op.create_index("ix_policies_publish_date", "policies", ["publish_date"])
    op.create_index("ix_policies_region", "policies", ["region"])

    # 2. knowledge_bases 增 is_public 标志
    op.add_column(
        "knowledge_bases",
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("ix_knowledge_bases_is_public", "knowledge_bases", ["is_public"])

    # 3. 播种系统公开租户(幂等：已存在则跳过)
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, plan, status, is_personal, monthly_token_limit) "
            "VALUES (:id, :name, :slug, 'free', 'active', false, 0) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(id=_PUBLIC_TENANT_ID, name="公开政策库", slug=_PUBLIC_TENANT_ID)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DELETE FROM tenants WHERE id = :id").bindparams(id=_PUBLIC_TENANT_ID))
    op.drop_index("ix_knowledge_bases_is_public", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "is_public")
    op.drop_index("ix_policies_region", table_name="policies")
    op.drop_index("ix_policies_publish_date", table_name="policies")
    op.drop_index("ix_policies_source_url", table_name="policies")
    op.drop_table("policies")
