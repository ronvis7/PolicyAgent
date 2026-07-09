"""add source_crawl_states (per-source last crawl run, so 0-result crawls still update "最近更新")

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-09

「数据来源」页"最近更新"原取 MAX(policies.crawled_at)，抓到 0 条时无政策行被写、时间戳不动，
一直显示"尚未抓取"。本表按 source 记录每次抓取运行时刻+结果计数(与是否入库无关)，纯新增表，
向后兼容(无记录时回落 MAX(crawled_at))。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "source_crawl_states",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "last_crawled_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"),
            nullable=False,
        ),
        sa.Column("last_new_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_crawled_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("source"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("source_crawl_states")
