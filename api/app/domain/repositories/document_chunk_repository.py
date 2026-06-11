from typing import Protocol, Optional, List, Tuple

from app.domain.models.document_chunk import DocumentChunk


class DocumentChunkRepository(Protocol):
    """文档切片数据仓库

    向量(embedding)的读写在此层封装，应用服务不直接依赖 pgvector SQL(见 ADR-001)。
    """

    async def save(self, chunk: DocumentChunk, embedding: Optional[List[float]] = None) -> None:
        """新增或更新切片，向量单独传入(为None表示尚未向量化)"""
        ...

    async def add_many(self, chunks: List[Tuple[DocumentChunk, Optional[List[float]]]]) -> None:
        """批量新增切片(及其向量)，用于入库流水线"""
        ...

    async def delete_by_knowledge_file(self, knowledge_file_id: str, tenant_id: str) -> None:
        """删除某知识库文件的全部切片(重解析前清理，要求归属该租户)"""
        ...

    async def search_similar(
        self,
        knowledge_base_id: str,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Tuple[DocumentChunk, float]]:
        """在某知识库内做向量相似检索，返回(切片, 相似度)列表(相似度越大越相关)"""
        ...
