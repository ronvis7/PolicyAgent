"""add RAG tables (knowledge_bases/knowledge_files/document_chunks) and pgvector

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-11

RAG R1 数据地基：启用 pgvector 扩展，新增三张表——知识库、知识库文件(带处理
状态机)、文档切片(含 vector(1024) 列)。向量列建 HNSW 余弦索引；HNSW 在空表上
即可建立并随插入增量构建，规避 ivfflat 需预先训练 lists 的问题。

向量维度 1024 必须与 config.yaml embed_config.dimension 及 ORM 中
DocumentChunkModel.EMBEDDING_DIM 严格一致。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    """Upgrade schema."""
    # 0. 启用 pgvector 扩展(镜像 pgvector/pgvector:pg16 已内置)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. 知识库表
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("description", sa.String(length=1024), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("type", sa.String(length=50), server_default=sa.text("'general'::character varying"), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_bases_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_knowledge_bases_tenant_id_tenants", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_knowledge_bases_owner_id_users", ondelete="SET NULL"),
    )
    op.create_index("ix_knowledge_bases_tenant_id", "knowledge_bases", ["tenant_id"])
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"])

    # 2. 知识库文件表(带处理状态机)
    op.create_table(
        "knowledge_files",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=True),
        sa.Column("file_id", sa.String(length=255), nullable=True),
        sa.Column("filename", sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'uploaded'::character varying"), nullable=False),
        sa.Column("error_message", sa.String(length=1024), server_default=sa.text("''::character varying"), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_files_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_knowledge_files_tenant_id_tenants", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], name="fk_knowledge_files_kb_id_knowledge_bases", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_knowledge_files_owner_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], name="fk_knowledge_files_file_id_files", ondelete="SET NULL"),
    )
    op.create_index("ix_knowledge_files_tenant_id", "knowledge_files", ["tenant_id"])
    op.create_index("ix_knowledge_files_knowledge_base_id", "knowledge_files", ["knowledge_base_id"])
    op.create_index("ix_knowledge_files_owner_id", "knowledge_files", ["owner_id"])
    op.create_index("ix_knowledge_files_file_id", "knowledge_files", ["file_id"])

    # 3. 文档切片表(含 vector(1024) 列)
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=255), nullable=False),
        sa.Column("knowledge_file_id", sa.String(length=255), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''::text"), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_document_chunks_tenant_id_tenants", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], name="fk_document_chunks_kb_id_knowledge_bases", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_file_id"], ["knowledge_files.id"], name="fk_document_chunks_kf_id_knowledge_files", ondelete="CASCADE"),
    )
    op.create_index("ix_document_chunks_tenant_id", "document_chunks", ["tenant_id"])
    op.create_index("ix_document_chunks_knowledge_base_id", "document_chunks", ["knowledge_base_id"])
    op.create_index("ix_document_chunks_knowledge_file_id", "document_chunks", ["knowledge_file_id"])

    # 4. 向量列 HNSW 余弦相似度索引(空表即可建立，随插入增量构建)
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.drop_index("ix_document_chunks_knowledge_file_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_knowledge_base_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_tenant_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_knowledge_files_file_id", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_owner_id", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_knowledge_base_id", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_tenant_id", table_name="knowledge_files")
    op.drop_table("knowledge_files")

    op.drop_index("ix_knowledge_bases_owner_id", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_tenant_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")

    # 不在 downgrade 中 DROP EXTENSION vector：其它对象或库可能仍依赖该扩展
