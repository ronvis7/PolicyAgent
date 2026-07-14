"""add contest sources, subscriptions, and contest metadata

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None

_OFFICIAL = ("wnd-contest", "gxt-contest", "cqkjj-contest", "cqjjw-contest", "cnmaker-contest")


def upgrade() -> None:
    op.add_column("policies", sa.Column("item_type", sa.String(16), nullable=False, server_default=sa.text("'policy'")))
    op.add_column("policies", sa.Column("origin_type", sa.String(16), nullable=False, server_default=sa.text("'official'")))
    op.add_column("policies", sa.Column("source_name", sa.String(255), nullable=False, server_default=sa.text("''")))
    op.create_index("ix_policies_item_type", "policies", ["item_type"])
    op.create_index("ix_policies_origin_type", "policies", ["origin_type"])
    op.execute("UPDATE policies SET item_type = 'competition' WHERE source IN (" + ",".join("'" + x + "'" for x in _OFFICIAL) + ")")
    op.execute("""
        UPDATE policies SET source_name = CASE source
            WHEN 'wnd-contest' THEN '无锡高新区（新吴区）门户·大赛通知'
            WHEN 'gxt-contest' THEN '江苏省工信厅门户·大赛通知'
            WHEN 'cqkjj-contest' THEN '重庆市科技局门户·大赛通知'
            WHEN 'cqjjw-contest' THEN '重庆市经信委门户·大赛通知'
            WHEN 'cnmaker-contest' THEN '创客中国官网·全国中小企业创新创业大赛'
            ELSE source_name
        END
        WHERE source IN ('wnd-contest', 'gxt-contest', 'cqkjj-contest', 'cqjjw-contest', 'cnmaker-contest')
    """)

    op.create_table(
        "contest_sources",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region", sa.String(128), nullable=False, server_default="全国"),
        sa.Column("home_url", sa.String(1024), nullable=False),
        sa.Column("adapter_type", sa.String(64), nullable=False),
        sa.Column("adapter_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
    )
    op.create_index("ix_contest_sources_key", "contest_sources", ["key"])
    op.create_table(
        "contest_subscriptions",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
        sa.UniqueConstraint("tenant_id", "keyword", name="uq_contest_subscriptions_tenant_keyword"),
    )
    op.create_index("ix_contest_subscriptions_tenant_id", "contest_subscriptions", ["tenant_id"])
    op.create_table(
        "contest_discovery_hits",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.String(255), sa.ForeignKey("contest_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", sa.String(255), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(0)")),
        sa.UniqueConstraint("tenant_id", "policy_id", name="uq_contest_discovery_hits_tenant_policy"),
    )
    op.create_index("ix_contest_discovery_hits_tenant_id", "contest_discovery_hits", ["tenant_id"])

    contest_sources = sa.table("contest_sources", sa.column("id", sa.String), sa.column("key", sa.String), sa.column("name", sa.String), sa.column("region", sa.String), sa.column("home_url", sa.String), sa.column("adapter_type", sa.String), sa.column("adapter_config", postgresql.JSONB), sa.column("enabled", sa.Boolean))
    op.bulk_insert(contest_sources, [
        {"id": "contest-wnd", "key": "wnd-contest", "name": "无锡高新区(新吴区)门户·大赛通知", "region": "江苏省无锡市新吴区", "home_url": "https://www.wnd.gov.cn", "adapter_type": "wnd", "adapter_config": {"title_keyword": "大赛"}, "enabled": True},
        {"id": "contest-gxt", "key": "gxt-contest", "name": "江苏省工信厅门户·大赛通知", "region": "江苏省", "home_url": "https://gxt.jiangsu.gov.cn", "adapter_type": "gxt", "adapter_config": {"title_keyword": "大赛"}, "enabled": True},
        {"id": "contest-cqkjj", "key": "cqkjj-contest", "name": "重庆市科技局门户·大赛通知", "region": "重庆市", "home_url": "https://kjj.cq.gov.cn", "adapter_type": "cq", "adapter_config": {"base_url": "https://kjj.cq.gov.cn", "column_path": "/zwxx_176/tzgg/", "title_keyword": "大赛"}, "enabled": True},
        {"id": "contest-cqjjw", "key": "cqjjw-contest", "name": "重庆市经信委门户·大赛通知", "region": "重庆市", "home_url": "https://jjxxw.cq.gov.cn", "adapter_type": "cq", "adapter_config": {"base_url": "https://jjxxw.cq.gov.cn", "column_path": "/zwgk_213/gsgg/", "title_keyword": "大赛"}, "enabled": True},
        {"id": "contest-cnmaker", "key": "cnmaker-contest", "name": "创客中国官网·全国中小企业创新创业大赛", "region": "全国", "home_url": "https://www.cnmaker.org.cn", "adapter_type": "cnmaker", "adapter_config": {}, "enabled": True},
    ])


def downgrade() -> None:
    op.drop_table("contest_discovery_hits")
    op.drop_table("contest_subscriptions")
    op.drop_table("contest_sources")
    op.drop_index("ix_policies_origin_type", table_name="policies")
    op.drop_index("ix_policies_item_type", table_name="policies")
    op.drop_column("policies", "source_name")
    op.drop_column("policies", "origin_type")
    op.drop_column("policies", "item_type")
