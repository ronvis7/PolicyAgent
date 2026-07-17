"""公开政策入库编排：爬取 → 结构化 upsert → 向量双写。

主线②的写入侧。结构化 upsert 入 policies 全局表(按 source_url 去重)；正文复用
RAG 分块/Embedding 流水线写入全局公开知识库(挂系统租户 'public' 满足既有外键)，
为后续③匹配/接问AI 提供语义检索底座。向量双写按 source_url 派生确定性 file id，
保证重复入库幂等(先删旧切片再写)。
"""

import asyncio
import logging
import uuid
from datetime import date, datetime
from typing import Awaitable, Callable, Dict, List, Optional, Set

from app.application.errors.exceptions import BadRequestError
from app.domain.external.embedding import EmbeddingProvider
from app.domain.external.llm import LLM
from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.knowledge_base import KnowledgeBase
from app.domain.models.knowledge_file import FileStatus, KnowledgeFile
from app.domain.models.parsed_document import ParsedPage
from app.domain.models.policy import Policy
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.chunker import chunk_pages
from app.domain.services.deadline_extractor import extract_deadline

logger = logging.getLogger(__name__)

# 公开政策库的系统归属(见迁移 e6f7a8b9c0d1 播种的系统租户)
PUBLIC_TENANT_ID = "public"
PUBLIC_KB_ID = "public-policy-kb"
PUBLIC_KB_NAME = "公开政策库"
# 由 source_url 派生确定性 file id 的命名空间，保证重复入库幂等
_FILE_ID_NAMESPACE = uuid.UUID("6f1c0e2a-0000-4000-8000-000000000001")


def _dedupe_by_source_url(policies: List[Policy]) -> List[Policy]:
    """同批政策按 source_url 去重(保留首见)，返回新列表。"""
    seen: set = set()
    unique: List[Policy] = []
    for policy in policies:
        if policy.source_url in seen:
            continue
        seen.add(policy.source_url)
        unique.append(policy)
    return unique


def _deadline_passed(policy: Policy, today: Optional[date] = None) -> bool:
    """申报截止已抽取且已过期(未抽出截止的不判定，交爬虫层时效窗口兜底)。"""
    deadline = policy.apply_deadline
    return deadline is not None and deadline < (today or date.today())


class PolicyIngestService:
    """公开政策入库编排服务(按来源选择爬虫 + 结构化 upsert + 向量双写)"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        crawlers: Dict[str, PolicyCrawler],
        embedding: EmbeddingProvider,
        llm: Optional[LLM] = None,
        on_new_policies: Optional[Callable[[str, List[Policy]], Awaitable[None]]] = None,
        skip_expired_sources: Optional[Set[str]] = None,
        source_metadata: Optional[Dict[str, tuple[str, str, str]]] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._crawlers = crawlers
        self._embedding = embedding
        # 用于从正文抽取申报截止日期(主线⑤)；缺省(None)则跳过抽取，保持向后兼容/可离线单测。
        self._llm = llm
        # 新增政策回调(source, 本次首次入库的政策)：供"新赛事即推"等通知接线，
        # best-effort 调用(回调异常不影响入库)；缺省(None)零行为变化。
        self._on_new_policies = on_new_policies
        # 过期即失效的来源集合(赛事子源，registry.competition_source_keys())：
        # 抽出申报截止且已过期的条目不入库不推送。缺省空集=不跳过，政策来源不受影响。
        self._skip_expired_sources = skip_expired_sources or set()
        # source -> (item_type, origin_type, display_name); 未配置时保持旧政策语义。
        self._source_metadata = source_metadata or {}
        # Dynamic sources are temporarily registered for a single run.  Serialise
        # those registrations so a manual run cannot replace a scheduled crawler.
        self._dynamic_ingest_lock = asyncio.Lock()
        self._skip_index_sources: Set[str] = set()

    async def ingest(self, source: str, max_pages: int = 1) -> Dict[str, object]:
        """按来源(source)抓取并入库，返回 {source, crawled, upserted, new, indexed} 计数。

        结构化 upsert 必做；向量双写为逐篇 best-effort(单篇失败不影响整批与结构化结果)。
        new=本次首次入库(source_url 此前不存在)的条数，入库完成后经 on_new_policies
        回调通知(如飞书推送新赛事)。
        """
        crawler = self._crawlers.get(source)
        if crawler is None:
            raise BadRequestError(f"未知的政策来源：{source}")
        # 同批按 source_url 去重后再进入后续所有环节：gxt dataproxy 分页窗口重叠会跨页
        # 返回重复条目，重复 save 在同一事务内会双双 INSERT 撞唯一约束导致整批回滚。
        policies = _dedupe_by_source_url(await crawler.crawl(max_pages))
        crawled = len(policies)

        item_type, origin_type, source_name = self._source_metadata.get(
            source, ("policy", "official", source),
        )
        for policy in policies:
            policy.item_type = item_type
            policy.origin_type = origin_type
            policy.source_name = source_name

        for policy in policies:
            await self._enrich_deadline(policy)

        # 赛事来源：报名截止已过=机会失效，跳过入库/向量化/推送(省存储、群不收过期比赛)
        skipped_expired = 0
        if source in self._skip_expired_sources:
            fresh = [p for p in policies if not _deadline_passed(p)]
            skipped_expired = len(policies) - len(fresh)
            policies = fresh

        new_policies = await self._detect_new(policies)

        upserted = 0
        async with self._uow_factory() as uow:
            for policy in policies:
                await uow.policy.save(policy)
                upserted += 1

        indexed = 0
        if source not in self._skip_index_sources:
            kb = await self._ensure_public_kb()
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

        summary = {
            "source": source, "crawled": crawled, "upserted": upserted,
            "new": len(new_policies), "indexed": indexed,
            "skipped_expired": skipped_expired, "item_type": item_type,
        }
        logger.info(f"公开政策入库完成: {summary}")

        # 记录本次抓取运行(即使 0 条入库)，供「数据来源」页"最近更新"如实反映跑过
        async with self._uow_factory() as uow:
            await uow.policy.record_crawl(source, datetime.now(), len(new_policies), crawled)

        await self._notify_new(source, new_policies)
        return summary

    async def ingest_with_crawler(
        self, source: str, crawler: PolicyCrawler, name: str, max_pages: int = 1,
        origin_type: str = "official", index: bool = True,
    ) -> Dict[str, object]:
        """用平台已验证模板构造的动态赛事来源入库。"""
        async with self._dynamic_ingest_lock:
            old_crawler = self._crawlers.get(source)
            old_metadata = self._source_metadata.get(source)
            self._crawlers[source] = crawler
            self._source_metadata[source] = ("competition", origin_type, name)
            self._skip_expired_sources.add(source)
            if not index:
                self._skip_index_sources.add(source)
            try:
                return await self.ingest(source, max_pages)
            finally:
                if old_crawler is None:
                    self._crawlers.pop(source, None)
                else:
                    self._crawlers[source] = old_crawler
                if old_metadata is None:
                    self._source_metadata.pop(source, None)
                else:
                    self._source_metadata[source] = old_metadata
                if not index:
                    self._skip_index_sources.discard(source)

    async def _detect_new(self, policies: List[Policy]) -> List[Policy]:
        """入库前按 source_url 批量比对存量，返回本次首次入库的政策(同批重复去重)。"""
        if not policies:
            return []
        urls = [p.source_url for p in policies]
        async with self._uow_factory() as uow:
            existing = await uow.policy.list_by_source_urls(urls)
        existing_urls = {p.source_url for p in existing}

        seen: set = set()
        new_policies: List[Policy] = []
        for policy in policies:
            # 同批跨页重复(如 gxt dataproxy 分页重叠)只算一次
            if policy.source_url in existing_urls or policy.source_url in seen:
                continue
            seen.add(policy.source_url)
            new_policies.append(policy)
        return new_policies

    async def _notify_new(self, source: str, new_policies: List[Policy]) -> None:
        """best-effort 通知新增政策(如飞书推送新赛事)；回调异常只记 warning，不冒泡。"""
        if self._on_new_policies is None or not new_policies:
            return
        try:
            await self._on_new_policies(source, new_policies)
        except Exception as e:  # noqa: BLE001 — 通知为增强，绝不影响入库结果
            logger.warning(
                "新增政策通知回调失败 source=%s: %s: %s", source, type(e).__name__, e,
            )

    async def _enrich_deadline(self, policy: Policy) -> None:
        """best-effort 抽取申报截止情况写回政策；无 LLM/失败时保持 unknown，绝不阻断入库。"""
        if self._llm is None:
            return
        result = await extract_deadline(self._llm, policy.title, policy.body_text)
        policy.apply_deadline = result.deadline
        policy.apply_window_text = result.window_text
        policy.deadline_status = result.status

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
