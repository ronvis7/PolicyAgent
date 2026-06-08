import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    text,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.tenant import Tenant


class TenantModel(Base):
    """租户(组织)ORM模型"""
    __tablename__ = "tenants"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_tenants_id"),
        UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )  # 租户id
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 租户名称
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 唯一标识
    plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'free'::character varying"),
    )  # 套餐
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'active'::character varying"),
    )  # 状态
    monthly_token_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )  # 月度token配额，0表示不限制
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 更新时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 创建时间

    @classmethod
    def from_domain(cls, tenant: Tenant) -> "TenantModel":
        """从领域模型创建ORM模型"""
        return cls(**tenant.model_dump(mode="json"))

    def to_domain(self) -> Tenant:
        """将ORM模型转换为领域模型"""
        return Tenant.model_validate(self, from_attributes=True)

    def update_from_domain(self, tenant: Tenant) -> None:
        """从领域模型更新数据"""
        for field, value in tenant.model_dump(mode="json").items():
            setattr(self, field, value)
