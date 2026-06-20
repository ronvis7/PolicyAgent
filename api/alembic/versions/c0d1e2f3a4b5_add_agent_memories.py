"""add agent_memories table (cross-session agent long-term memory)

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-20

Agent 跨会话长期记忆(ADR 004)：每条记忆是一句自然语言事实/偏好，按租户聚合。
以 id 为主键、tenant_id 建索引作为召回/隔离边界，租户删除时级联清理。纯新增表，向后兼容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("source_session_id", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            ondelete="CASCADE", name="fk_agent_memories_tenant_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_memories_id"),
    )
    op.create_index(
        "ix_agent_memories_tenant_id", "agent_memories", ["tenant_id"], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_agent_memories_tenant_id", table_name="agent_memories")
    op.drop_table("agent_memories")
