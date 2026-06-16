"""公开政策入库编排：爬取 → 结构化 upsert → 向量双写。

主线②的写入侧。结构化 upsert 入 policies 全局表(按 source_url 去重)；正文复用
RAG 分块/Embedding 流水线写入全局公开知识库(挂系统租户 'public' 满足既有外键)，
为后续③匹配/接问AI 提供语义检索底座。向量双写按 source_url 派生确定性 file id，
保证重复入库幂等(先删旧切片再写)。
"""

import logging
import uuid
from typing import Callable, Dict, List

from app.application.errors.exceptions import BadRequestError
from app.domain.external.embedding import EmbeddingProvider
from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.knowledge_base import KnowledgeBase
from app.domain.models.knowledge_file import FileStatus, KnowledgeFile
from app.domain.models.parsed_document import ParsedPage
from app.domain.models.policy import Policy
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.chunker import chunk_pages

logger = logging.getLogger(__name__)

# 公开政策库的系统归属(见迁移 e6f7a8b9c0d1 播种的系统租户)
PUBLIC_TENANT_ID = "public"
PUBLIC_KB_ID = "public-policy-kb"
PUBLIC_KB_NAME = "公开政策库"
# 由 source_url 派生确定性 file id 的命名空间，保证重复入库幂等
_FILE_ID_NAMESPACE = uuid.UUID("6f1c0e2a-0000-4000-8000-000000000001")


class PolicyIngestService:
    """公开政策入库编排服务(按来源选择爬虫 + 结构化 upsert + 向量双写)"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        crawlers: Dict[str, PolicyCrawler],
        embedding: EmbeddingProvider,
    ) -> None:
        self._uow_factory = uow_factory
        self._crawlers = crawlers
        self._embedding = embedding

    async def ingest(self, source: str, max_pages: int = 1) -> Dict[str, object]:
        """按来源(source)抓取并入库，返回 {source, crawled, upserted, indexed} 计数。

        结构化 upsert 必做；向量双写为逐篇 best-effort(单篇失败不影响整批与结构化结果)。
        """
        crawler = self._crawlers.get(source)
        if crawler is None:
            raise BadRequestError(f"未知的政策来源：{source}")
        policies = await crawler.crawl(max_pages)

        upserted = 0
        async with self._uow_factory() as uow:
            for policy in policies:
                await uow.policy.save(policy)
                upserted += 1

        kb = await self._ensure_public_kb()
        indexed = 0
        for policy in policies:
            if not policy.body_text.strip():
                continue
            try:
                await self._index_policy(kb, policy)
                indexed += 1
            except Exception as e:
                logger.warning(
                    f"政策向量双写失败[{policy.source_url}]: {type(e).__name__}: {e}"
                )

        summary = {"source": source, "crawled": len(policies), "upserted": upserted, "indexed": indexed}
        logger.info(f"公开政策入库完成: {summary}")
        return summary

    async def _ensure_public_kb(self) -> KnowledgeBase:
        """获取或创建全局公开政策知识库(固定 id，挂系统公开租户)"""
        async with self._uow_factory() as uow:
            kb = await uow.knowledge_base.get_by_id(PUBLIC_KB_ID)
            if kb:
                return kb
            kb = KnowledgeBase(
                id=PUBLIC_KB_ID,
                tenant_id=PUBLIC_TENANT_ID,
                name=PUBLIC_KB_NAME,
                description="主线②爬取入库的全局公开政策(跨租户共享)",
                is_public=True,
                embedding_model=self._embedding.model_name,
            )
            await uow.knowledge_base.save(kb)
        return kb

    async def _index_policy(self, kb: KnowledgeBase, policy: Policy) -> None:
        """将单篇政策正文分块+向量化写入公开库(按 source_url 幂等替换旧切片)"""
        pieces = chunk_pages([ParsedPage(page_number=1, text=policy.body_text)])
        if not pieces:
            return

        vectors = await self._embedding.embed_documents([p.content for p in pieces])
        file_id = str(uuid.uuid5(_FILE_ID_NAMESPACE, policy.source_url))

        kf = KnowledgeFile(
            id=file_id,
            tenant_id=PUBLIC_TENANT_ID,
            knowledge_base_id=kb.id,
            file_id=None,  # 政策为爬取正文，无原始 COS 文件
            filename=policy.title or policy.source_url,
            status=FileStatus.INDEXED,
            chunk_count=len(pieces),
        )
        chunks_with_vectors: List = [
            (
                DocumentChunk(
                    tenant_id=PUBLIC_TENANT_ID,
                    knowledge_base_id=kb.id,
                    knowledge_file_id=file_id,
                    chunk_index=piece.chunk_index,
                    content=piece.content,
                    token_count=piece.token_count,
                    chunk_metadata={
                        "page": piece.metadata.get("page", 1),
                        "source_url": policy.source_url,
                        "title": policy.title,
                    },
                ),
                vector,
            )
            for piece, vector in zip(pieces, vectors)
        ]

        async with self._uow_factory() as uow:
            await uow.knowledge_file.save(kf)
            # 先 flush 父行 knowledge_files：chunk 与 file 的 ORM 模型间未声明 relationship，
            # 同一事务 commit 时 flush 顺序不定，不先落父行会导致 document_chunks 子行
            # 先 INSERT 而违反外键 fk_document_chunks_kf_id_knowledge_files。
            await uow.flush()
            await uow.document_chunk.delete_by_knowledge_file(file_id, PUBLIC_TENANT_ID)
            await uow.document_chunk.add_many(chunks_with_vectors)
