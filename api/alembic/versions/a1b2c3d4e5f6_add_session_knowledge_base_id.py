"""add sessions.knowledge_base_id (会话级 KB scope 绑定)

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-06-12

会话级知识库 scope 选择器：给 sessions 增加可空外键 knowledge_base_id，指向
knowledge_bases。检索工具以该绑定为硬限定范围(存在时只搜该库)，None 表示全库。
ON DELETE SET NULL：删除知识库时自动解绑相关会话，避免悬挂引用。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("knowledge_base_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_sessions_knowledge_base_id", "sessions", ["knowledge_base_id"],
    )
    op.create_foreign_key(
        "fk_sessions_knowledge_base_id",
        "sessions",
        "knowledge_bases",
        ["knowledge_base_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_sessions_knowledge_base_id", "sessions", type_="foreignkey")
    op.drop_index("ix_sessions_knowledge_base_id", table_name="sessions")
    op.drop_column("sessions", "knowledge_base_id")
