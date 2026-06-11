import uuid
from datetime import datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    text,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.document_chunk import DocumentChunk

# 向量维度，必须与 config.yaml embed_config.dimension 一致(1024 对 text-embedding-v3
# 与未来本地 bge-m3 前向兼容)。改动需同步迁移与该常量。
EMBEDDING_DIM = 1024


class DocumentChunkModel(Base):
    """文档切片ORM模型(含pgvector向量列)"""
    __tablename__ = "document_chunks"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_document_chunks_id"),
    )

    id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )  # 切片id
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
    knowledge_file_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("knowledge_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 所属知识库文件id
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )  # 切片在文件内的顺序索引
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
    )  # 切片文本内容
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )  # 切片token数
    chunk_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )  # 元数据(页码/位置等，供引用回答)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True,
    )  # 向量(向量化前为NULL；持久化/检索由Repository承载)
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
    def from_domain(
        cls,
        chunk: DocumentChunk,
        embedding: Optional[List[float]] = None,
    ) -> "DocumentChunkModel":
        """从领域模型创建ORM模型，向量单独传入(领域模型不含embedding)"""
        return cls(**chunk.model_dump(), embedding=embedding)

    def to_domain(self) -> DocumentChunk:
        """将ORM模型转换为领域模型(不含向量)"""
        return DocumentChunk.model_validate(self, from_attributes=True)

    def update_from_domain(self, chunk: DocumentChunk) -> None:
        """从领域模型更新数据(不触碰向量)"""
        for field, value in chunk.model_dump().items():
            setattr(self, field, value)
