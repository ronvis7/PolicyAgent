import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    text,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.membership import Membership


class MembershipModel(Base):
    """成员关系ORM模型，用户与租户的多对多关联"""
    __tablename__ = "memberships"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_memberships_id"),
        UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),
    )

    id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )  # 成员关系id
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 用户id
    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 租户id
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'member'::character varying"),
    )  # 角色
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'active'::character varying"),
    )  # 状态
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
    def from_domain(cls, membership: Membership) -> "MembershipModel":
        """从领域模型创建ORM模型"""
        return cls(**membership.model_dump(mode="json"))

    def to_domain(self) -> Membership:
        """将ORM模型转换为领域模型"""
        return Membership.model_validate(self, from_attributes=True)

    def update_from_domain(self, membership: Membership) -> None:
        """从领域模型更新数据"""
        for field, value in membership.model_dump(mode="json").items():
            setattr(self, field, value)
