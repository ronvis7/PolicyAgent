"""tighten sessions.tenant_id to NOT NULL (P3 isolation enforcement)

Revision ID: c3d4e5f6a7b8
Revises: b7c1d2e3f4a5
Create Date: 2026-06-08

P3 启用会话隔离后，所有新会话创建均会写入 tenant_id，存量数据已在 P1 回填，
故将 sessions.tenant_id 收紧为 NOT NULL。files.tenant_id 暂保持可空，待 P3.5
完成 agent 生成文件的租户标记后再统一收紧。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 默认租户id(与 P1 迁移一致，用于兜底回填)
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Upgrade schema."""
    # 1.兜底回填任何残留的 NULL tenant_id 到默认租户
    op.execute(
        sa.text("UPDATE sessions SET tenant_id = :id WHERE tenant_id IS NULL").bindparams(id=DEFAULT_TENANT_ID)
    )
    # 2.收紧为 NOT NULL
    op.alter_column("sessions", "tenant_id", existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("sessions", "tenant_id", existing_type=sa.String(length=255), nullable=True)
