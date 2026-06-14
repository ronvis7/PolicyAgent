import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    String,
    DateTime,
    ForeignKey,
    text,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.knowledge_base import KnowledgeBase


class KnowledgeBaseModel(Base):
    """知识库ORM模型"""
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_knowledge_bases_id"),
    )

    id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )  # 知识库id
    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 所属租户id(行级隔离)
    owner_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # 创建者用户id
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 知识库名称
    description: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 知识库描述
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'general'::character varying"),
    )  # 知识库类型(工厂分发)
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        index=True,
    )  # 是否为全局公开库(跨租户共享)
    embedding_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 该库使用的embedding模型名
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
    def from_domain(cls, knowledge_base: KnowledgeBase) -> "KnowledgeBaseModel":
        """从领域模型创建ORM模型"""
        return cls(**knowledge_base.model_dump())

    def to_domain(self) -> KnowledgeBase:
        """将ORM模型转换为领域模型"""
        return KnowledgeBase.model_validate(self, from_attributes=True)

    def update_from_domain(self, knowledge_base: KnowledgeBase) -> None:
        """从领域模型更新数据"""
        for field, value in knowledge_base.model_dump().items():
            setattr(self, field, value)
