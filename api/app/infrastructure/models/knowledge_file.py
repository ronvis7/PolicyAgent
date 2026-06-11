import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    text,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.knowledge_file import KnowledgeFile


class KnowledgeFileModel(Base):
    """知识库文件ORM模型"""
    __tablename__ = "knowledge_files"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_knowledge_files_id"),
    )

    id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )  # 知识库文件id
    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 所属租户id(行级隔离)
    knowledge_base_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 所属知识库id
    owner_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # 上传者用户id
    file_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # 关联的原始文件id(files表)
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 文件名(冗余存储)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'uploaded'::character varying"),
    )  # 处理状态(状态机)
    error_message: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 失败原因
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )  # 切片数量
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
    def from_domain(cls, knowledge_file: KnowledgeFile) -> "KnowledgeFileModel":
        """从领域模型创建ORM模型"""
        return cls(**knowledge_file.model_dump())

    def to_domain(self) -> KnowledgeFile:
        """将ORM模型转换为领域模型"""
        return KnowledgeFile.model_validate(self, from_attributes=True)

    def update_from_domain(self, knowledge_file: KnowledgeFile) -> None:
        """从领域模型更新数据"""
        for field, value in knowledge_file.model_dump().items():
            setattr(self, field, value)
