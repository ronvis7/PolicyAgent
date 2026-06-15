"""add policy_matches table (workbench feed, materialized opportunity matches)

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-06-15

工作台 Feed(④)：把③即时匹配结果物化为持久化信息流。每租户一机会一条
((tenant_id, policy_id) 唯一)，计算快照直接落列(列表单表查询免 N+1)，
status 状态机(unread/read/applied/ignored)驱动未读红点。type 为机会类型扩展位
(policy/qualification/competition，⑥ 资质/比赛复用本流)。纯新增表，向后兼容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "policy_matches",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), server_default=sa.text("'policy'"), nullable=False),
        sa.Column("policy_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), server_default=sa.text("''"), nullable=False),
        sa.Column("issuer", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(length=1024), server_default=sa.text("''"), nullable=False),
        sa.Column("region", sa.String(length=128), server_default=sa.text("''"), nullable=False),
        sa.Column("score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("structured_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("semantic_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "matched_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'unread'"), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_matches"),
        sa.UniqueConstraint("tenant_id", "policy_id", name="uq_policy_matches_tenant_policy"),
    )
    op.create_index("ix_policy_matches_tenant_id", "policy_matches", ["tenant_id"])
    op.create_index("ix_policy_matches_status", "policy_matches", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_policy_matches_status", table_name="policy_matches")
    op.drop_index("ix_policy_matches_tenant_id", table_name="policy_matches")
    op.drop_table("policy_matches")
