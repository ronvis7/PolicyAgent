from typing import Optional, List, Tuple

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.document_chunk import DocumentChunk
from app.domain.repositories.document_chunk_repository import DocumentChunkRepository
from app.infrastructure.models import DocumentChunkModel


class DBDocumentChunkRepository(DocumentChunkRepository):
    """基于Postgres + pgvector的文档切片仓库

    向量读写细节(cosine_distance等)封装在此，应用服务不感知 pgvector。
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, chunk: DocumentChunk, embedding: Optional[List[float]] = None) -> None:
        """新增或更新切片，向量单独传入(为None表示尚未向量化)"""
        stmt = select(DocumentChunkModel).where(DocumentChunkModel.id == chunk.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            self.db_session.add(DocumentChunkModel.from_domain(chunk, embedding=embedding))
            return

        record.update_from_domain(chunk)
        if embedding is not None:
            record.embedding = embedding

    async def add_many(self, chunks: List[Tuple[DocumentChunk, Optional[List[float]]]]) -> None:
        """批量新增切片(及其向量)，用于入库流水线"""
        self.db_session.add_all(
            [DocumentChunkModel.from_domain(chunk, embedding=embedding) for chunk, embedding in chunks]
        )

    async def delete_by_knowledge_file(self, knowledge_file_id: str, tenant_id: str) -> None:
        """删除某知识库文件的全部切片(重解析前清理，要求归属该租户)"""
        stmt = delete(DocumentChunkModel).where(
            DocumentChunkModel.knowledge_file_id == knowledge_file_id,
            DocumentChunkModel.tenant_id == tenant_id,
        )
        await self.db_session.execute(stmt)

    async def search_similar(
        self,
        knowledge_base_id: str,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Tuple[DocumentChunk, float]]:
        """在某知识库内做向量相似检索，返回(切片, 相似度)列表(相似度越大越相关)"""
        # 余弦距离 ∈ [0, 2]，相似度 = 1 - 距离 ∈ [-1, 1]，越大越相关
        distance = DocumentChunkModel.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(DocumentChunkModel, distance)
            .where(
                DocumentChunkModel.knowledge_base_id == knowledge_base_id,
                DocumentChunkModel.tenant_id == tenant_id,
                DocumentChunkModel.embedding.is_not(None),
            )
            .order_by(distance.asc())
            .limit(top_k)
        )
        result = await self.db_session.execute(stmt)
        return [(record.to_domain(), 1.0 - float(dist)) for record, dist in result.all()]
