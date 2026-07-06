"""add tenant_settings.feishu_config (org-level Feishu webhook for contest push)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-06

组织级飞书群机器人 webhook 配置(前端设置页配置，替代部署级 env)：新赛事入库时按租户扇出
推送、按各租户"参赛关注地区"过滤。纯新增可空 JSONB 列，NULL=未开启推送，向后兼容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tenant_settings",
        sa.Column("feishu_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tenant_settings", "feishu_config")
