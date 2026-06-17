"""add policy apply deadline columns (proactive deadline reminders)

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-17

主线⑤ 主动提醒：政策表新增申报截止三列。截止日期由 LLM 从正文抽取(遵循"待核对"纪律)，
仅 deadline_status=extracted 时 apply_deadline 有值；apply_window_text 存原文窗口描述供
展示+人工核对；deadline_status ∈ extracted/rolling/unknown。纯新增列，向后兼容。
apply_deadline 建索引以支撑"临期"查询(按截止日期排序/筛选)。
同时把申报截止快照(apply_deadline/deadline_status)落到工作台 Feed 表 policy_matches，
使临期查询与 Feed 列表均为单表查询(免 N+1)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("policies", sa.Column("apply_deadline", sa.Date(), nullable=True))
    op.add_column(
        "policies",
        sa.Column(
            "apply_window_text", sa.Text(), server_default=sa.text("''"), nullable=False,
        ),
    )
    op.add_column(
        "policies",
        sa.Column(
            "deadline_status",
            sa.String(length=16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
    )
    op.create_index("ix_policies_apply_deadline", "policies", ["apply_deadline"])

    # 工作台 Feed 表同步截止快照(只需日期+状态，窗口文本看政策详情)
    op.add_column("policy_matches", sa.Column("apply_deadline", sa.Date(), nullable=True))
    op.add_column(
        "policy_matches",
        sa.Column(
            "deadline_status",
            sa.String(length=16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
    )
    op.create_index("ix_policy_matches_apply_deadline", "policy_matches", ["apply_deadline"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_policy_matches_apply_deadline", table_name="policy_matches")
    op.drop_column("policy_matches", "deadline_status")
    op.drop_column("policy_matches", "apply_deadline")

    op.drop_index("ix_policies_apply_deadline", table_name="policies")
    op.drop_column("policies", "deadline_status")
    op.drop_column("policies", "apply_window_text")
    op.drop_column("policies", "apply_deadline")
