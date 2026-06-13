"""add tenants.is_personal (personal workspace vs shared org)

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-06-13

引入"个人工作区"概念以支持注册时拆分"创建组织 / 加入组织"：
- 个人工作区(is_personal=true)：每个加入已有组织的用户自动获得，用于在被批准前
  以自己的 key 试用，不参与组织名唯一约束、不可被他人加入。
- 共享组织(is_personal=false)：组织名规范化后唯一(当前在应用层校验；存量数据可能
  存在历史重复，待清理后再补 DB 唯一索引)。

存量租户默认 is_personal=false(视为共享组织)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tenants",
        sa.Column("is_personal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tenants", "is_personal")
