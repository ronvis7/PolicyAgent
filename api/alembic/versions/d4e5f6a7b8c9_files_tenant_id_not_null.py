"""tighten files.tenant_id to NOT NULL (P3.5 file isolation)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-08

P3.5 后所有文件创建路径(用户上传 + agent 生成文件/截图)均会写入 tenant_id，
存量数据已在 P1 回填，故将 files.tenant_id 收紧为 NOT NULL。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 默认租户id(与 P1 迁移一致，用于兜底回填)
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Upgrade schema."""
    # 1.兜底回填任何残留的 NULL tenant_id 到默认租户
    op.execute(
        sa.text("UPDATE files SET tenant_id = :id WHERE tenant_id IS NULL").bindparams(id=DEFAULT_TENANT_ID)
    )
    # 2.收紧为 NOT NULL
    op.alter_column("files", "tenant_id", existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("files", "tenant_id", existing_type=sa.String(length=255), nullable=True)
