"""add multitenancy tables (tenants/users/memberships) and tenant scoping columns

Revision ID: b7c1d2e3f4a5
Revises: 9a750a2b019f
Create Date: 2026-06-08

P1 多租户地基：新增 tenants/users/memberships 三张表，并给 sessions/files
增加 tenant_id/owner_id 作用域列（本阶段为可空，回填到默认租户；P3 启用隔离
强制后再收紧为 NOT NULL）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "9a750a2b019f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 默认租户id，用于回填存量 sessions/files 数据
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 租户(组织)表
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("slug", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("plan", sa.String(length=50), server_default=sa.text("'free'::character varying"), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'active'::character varying"), nullable=False),
        sa.Column("monthly_token_limit", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tenants_id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    # 2. 用户表(全局身份)
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("password_hash", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("display_name", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'active'::character varying"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # 3. 成员关系表(用户<->租户 多对多 + 角色)
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default=sa.text("'member'::character varying"), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'active'::character varying"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_memberships_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_memberships_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_memberships_tenant_id_tenants", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"])

    # 4. 创建默认租户，用于承接存量数据
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, plan, status) "
            "VALUES (:id, 'Default Organization', 'default', 'enterprise', 'active')"
        ).bindparams(id=DEFAULT_TENANT_ID)
    )

    # 5. 给 sessions 增加作用域列(本阶段可空)
    op.add_column("sessions", sa.Column("tenant_id", sa.String(length=255), nullable=True))
    op.add_column("sessions", sa.Column("owner_id", sa.String(length=255), nullable=True))
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"])
    op.create_index("ix_sessions_owner_id", "sessions", ["owner_id"])
    op.create_foreign_key(
        "fk_sessions_tenant_id_tenants", "sessions", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_sessions_owner_id_users", "sessions", "users", ["owner_id"], ["id"], ondelete="SET NULL"
    )

    # 6. 给 files 增加作用域列(本阶段可空)
    op.add_column("files", sa.Column("tenant_id", sa.String(length=255), nullable=True))
    op.add_column("files", sa.Column("owner_id", sa.String(length=255), nullable=True))
    op.create_index("ix_files_tenant_id", "files", ["tenant_id"])
    op.create_index("ix_files_owner_id", "files", ["owner_id"])
    op.create_foreign_key(
        "fk_files_tenant_id_tenants", "files", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_files_owner_id_users", "files", "users", ["owner_id"], ["id"], ondelete="SET NULL"
    )

    # 7. 回填存量数据到默认租户
    op.execute(
        sa.text("UPDATE sessions SET tenant_id = :id WHERE tenant_id IS NULL").bindparams(id=DEFAULT_TENANT_ID)
    )
    op.execute(
        sa.text("UPDATE files SET tenant_id = :id WHERE tenant_id IS NULL").bindparams(id=DEFAULT_TENANT_ID)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # files 作用域列
    op.drop_constraint("fk_files_owner_id_users", "files", type_="foreignkey")
    op.drop_constraint("fk_files_tenant_id_tenants", "files", type_="foreignkey")
    op.drop_index("ix_files_owner_id", table_name="files")
    op.drop_index("ix_files_tenant_id", table_name="files")
    op.drop_column("files", "owner_id")
    op.drop_column("files", "tenant_id")

    # sessions 作用域列
    op.drop_constraint("fk_sessions_owner_id_users", "sessions", type_="foreignkey")
    op.drop_constraint("fk_sessions_tenant_id_tenants", "sessions", type_="foreignkey")
    op.drop_index("ix_sessions_owner_id", table_name="sessions")
    op.drop_index("ix_sessions_tenant_id", table_name="sessions")
    op.drop_column("sessions", "owner_id")
    op.drop_column("sessions", "tenant_id")

    # memberships / users / tenants
    op.drop_index("ix_memberships_tenant_id", table_name="memberships")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")
