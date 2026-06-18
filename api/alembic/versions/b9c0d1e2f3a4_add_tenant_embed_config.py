"""add tenant_settings.embed_config (租户级 Embedding BYO key)

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-18

双轨 Embedding(见 ADR 003)私有侧：给 tenant_settings 增加可空 JSONB 列 embed_config，
对称已有 llm_config。租户只 BYO api_key，base_url/model/dimension 在服务层解析时锁平台值
(维度恒 1024)。NULL 表示未覆盖，运行时回落平台默认(平台模型 + .env key)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tenant_settings",
        sa.Column("embed_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tenant_settings", "embed_config")
