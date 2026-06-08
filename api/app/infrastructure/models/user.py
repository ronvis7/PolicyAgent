import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    text,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.user import User


class UserModel(Base):
    """用户ORM模型"""
    __tablename__ = "users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_users_id"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )  # 用户id
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 邮箱
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 密码哈希
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 显示名称
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'active'::character varying"),
    )  # 状态
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )  # 是否为平台管理员
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )  # 最后登录时间
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
    def from_domain(cls, user: User) -> "UserModel":
        """从领域模型创建ORM模型"""
        return cls(**user.model_dump(mode="json"))

    def to_domain(self) -> User:
        """将ORM模型转换为领域模型"""
        return User.model_validate(self, from_attributes=True)

    def update_from_domain(self, user: User) -> None:
        """从领域模型更新数据"""
        for field, value in user.model_dump(mode="json").items():
            setattr(self, field, value)
