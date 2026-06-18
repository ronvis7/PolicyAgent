import logging
import os
import uuid
from typing import Callable, Dict, List, Tuple

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.application.errors.exceptions import NotFoundError, ServerRequestsError
from app.domain.external.document_parser import DocumentParser
from app.domain.external.embedding import EmbeddingProvider
from app.domain.external.file_storage import FileStorage
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.knowledge_base import KnowledgeBase, KnowledgeBaseType
from app.domain.models.knowledge_file import KnowledgeFile, FileStatus
from app.domain.models.parsed_document import ParsedPage
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.chunker import chunk_pages

logger = logging.getLogger(__name__)

# 收藏政策派生确定性 file id 的命名空间：同租户/同库内按 source_url 幂等(重复收藏走替换)
_COLLECTED_POLICY_NAMESPACE = uuid.UUID("6f1c0e2a-0000-4000-8000-000000000002")


class KnowledgeService:
    """知识库应用服务：知识库 CRUD + 文件上传 + 解析/分块/向量化入库流水线"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        file_storage: FileStorage,
        embedding: EmbeddingProvider,
        parser: DocumentParser,
    ) -> None:
        self._uow_factory = uow_factory
        self.file_storage = file_storage
        self.embedding = embedding
        self.parser = parser

    # ---------- 知识库 CRUD ----------

    async def create_knowledge_base(
        self, tenant_id: str, owner_id: str, name: str, description: str = "",
        type: KnowledgeBaseType = KnowledgeBaseType.GENERAL,
    ) -> KnowledgeBase:
        """新建知识库(归属当前租户与创建者)，绑定当前 embedding 模型"""
        kb = KnowledgeBase(
            tenant_id=tenant_id, owner_id=owner_id, name=name,
            description=description, type=type,
            embedding_model=self.embedding.model_name,
        )
        async with self._uow_factory() as uow:
            await uow.knowledge_base.save(kb)
        return kb

    async def list_knowledge_bases(self, tenant_id: str) -> List[KnowledgeBase]:
        """列出当前租户的全部知识库"""
        async with self._uow_factory() as uow:
            return await uow.knowledge_base.list_by_tenant(tenant_id)

    async def get_knowledge_base(self, kb_id: str, tenant_id: str) -> KnowledgeBase:
        """获取知识库(校验租户归属)"""
        async with self._uow_factory() as uow:
            kb = await uow.knowledge_base.get_by_id(kb_id, tenant_id=tenant_id)
        if not kb:
            raise NotFoundError(f"知识库[{kb_id}]不存在")
        return kb

    async def delete_knowledge_base(self, kb_id: str, tenant_id: str) -> None:
        """删除知识库(级联删除其文件与切片，校验租户归属)"""
        await self.get_knowledge_base(kb_id, tenant_id)  # 隔离守卫
        async with self._uow_factory() as uow:
            await uow.knowledge_base.delete(kb_id, tenant_id)

    # ---------- 文件上传 + 列表 ----------

    async def upload_file(
        self, kb_id: str, tenant_id: str, owner_id: str, upload_file: UploadFile,
    ) -> KnowledgeFile:
        """上传文件到知识库：存 COS + 建 KnowledgeFile(uploaded)，解析交由后台流水线"""
        # 1. 校验知识库归属
        await self.get_knowledge_base(kb_id, tenant_id)

        # 2. 先校验类型，避免上传不支持的文件到 COS 产生孤儿对象
        _, ext = os.path.splitext(upload_file.filename or "")
        if not self.parser.supports(ext):
            raise ServerRequestsError(f"暂不支持的文件类型: {ext or '(无扩展名)'}")

        # 3. 原始文件落 COS(创建 files 记录)
        file = await self.file_storage.upload_file(
            upload_file=upload_file, tenant_id=tenant_id, owner_id=owner_id,
        )

        # 4. 建知识库文件记录(待后台入库)
        kf = KnowledgeFile(
            tenant_id=tenant_id, knowledge_base_id=kb_id, owner_id=owner_id,
            file_id=file.id, filename=file.filename, status=FileStatus.UPLOADED,
        )
        async with self._uow_factory() as uow:
            await uow.knowledge_file.save(kf)
        return kf

    async def list_files(self, kb_id: str, tenant_id: str) -> List[KnowledgeFile]:
        """列出知识库下的文件(校验租户归属)"""
        await self.get_knowledge_base(kb_id, tenant_id)
        async with self._uow_factory() as uow:
            return await uow.knowledge_file.list_by_knowledge_base(kb_id, tenant_id)

    async def file_counts(self, tenant_id: str) -> Dict[str, int]:
        """统计当前租户各知识库的文件数 {kb_id: count}(单次分组查询，供列表卡片展示真实数量)"""
        async with self._uow_factory() as uow:
            return await uow.knowledge_file.count_by_tenant(tenant_id)

    # ---------- 从公开政策库收藏入私有政策库(ADR-003) ----------

    async def collect_policy(
        self, kb_id: str, tenant_id: str, owner_id: str, policy_id: str,
    ) -> KnowledgeFile:
        """把一篇公开政策的正文作为文档登记到私有政策库(向量化交后台流水线)。

        只允许收藏到 type=policy 的知识库；按 (租户, 库, source_url) 派生确定性 file id，
        重复收藏走幂等替换。仅建占位 KnowledgeFile(uploaded)，分块/向量化由后台执行
        (用当前租户 embedding key，见双轨 Embedding)。
        """
        kb = await self.get_knowledge_base(kb_id, tenant_id)  # 隔离守卫
        if kb.type != KnowledgeBaseType.POLICY:
            raise ServerRequestsError("只能收藏政策到「私有政策库」类型的知识库")

        async with self._uow_factory() as uow:
            policy = await uow.policy.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"政策[{policy_id}]不存在")
        if not policy.body_text.strip():
            raise ServerRequestsError("该政策无正文，无法收藏")

        file_id = str(uuid.uuid5(
            _COLLECTED_POLICY_NAMESPACE, f"{tenant_id}:{kb_id}:{policy.source_url}",
        ))
        kf = KnowledgeFile(
            id=file_id, tenant_id=tenant_id, knowledge_base_id=kb_id, owner_id=owner_id,
            file_id=None, filename=policy.title or policy.source_url,
            status=FileStatus.UPLOADED,
        )
        async with self._uow_factory() as uow:
            await uow.knowledge_file.save(kf)
        return kf

    async def collect_policies(
        self, kb_id: str, tenant_id: str, owner_id: str, policy_ids: List[str],
    ) -> Tuple[List[Tuple[KnowledgeFile, str]], List[str]]:
        """批量收藏多篇公开政策到私有政策库。

        库类型校验只做一次；逐篇 best-effort：政策缺失或正文为空则跳过（计入 skipped），
        不阻断其余收藏。返回 (collected=[(占位文件, policy_id)], skipped=[policy_id])，
        向量化由调用方按 collected 逐篇排后台任务。
        """
        kb = await self.get_knowledge_base(kb_id, tenant_id)  # 隔离守卫
        if kb.type != KnowledgeBaseType.POLICY:
            raise ServerRequestsError("只能收藏政策到「私有政策库」类型的知识库")

        collected: List[Tuple[KnowledgeFile, str]] = []
        skipped: List[str] = []
        async with self._uow_factory() as uow:
            for policy_id in policy_ids:
                policy = await uow.policy.get_by_id(policy_id)
                if not policy or not policy.body_text.strip():
                    skipped.append(policy_id)
                    continue
                file_id = str(uuid.uuid5(
                    _COLLECTED_POLICY_NAMESPACE, f"{tenant_id}:{kb_id}:{policy.source_url}",
                ))
                kf = KnowledgeFile(
                    id=file_id, tenant_id=tenant_id, knowledge_base_id=kb_id, owner_id=owner_id,
                    file_id=None, filename=policy.title or policy.source_url,
                    status=FileStatus.UPLOADED,
                )
                await uow.knowledge_file.save(kf)
                collected.append((kf, policy_id))
        return collected, skipped

    async def ingest_collected_policy(
        self, knowledge_file_id: str, tenant_id: str, policy_id: str,
    ) -> None:
        """后台：取政策正文→分块→向量化(租户 key)→落库，幂等替换旧切片。"""
        async with self._uow_factory() as uow:
            kf = await uow.knowledge_file.get_by_id(knowledge_file_id, tenant_id=tenant_id)
            policy = await uow.policy.get_by_id(policy_id)
        if not kf or not policy:
            logger.warning(f"收藏入库找不到文件[{knowledge_file_id}]或政策[{policy_id}]，跳过")
            return

        try:
            await self._update_status(kf, FileStatus.INDEXING)
            pieces = chunk_pages([ParsedPage(page_number=1, text=policy.body_text)])
            if not pieces:
                kf.chunk_count = 0
                await self._update_status(kf, FileStatus.INDEXED)
                return

            vectors = await self.embedding.embed_documents([p.content for p in pieces])
            chunks_with_vectors = [
                (
                    DocumentChunk(
                        tenant_id=tenant_id, knowledge_base_id=kf.knowledge_base_id,
                        knowledge_file_id=kf.id, chunk_index=piece.chunk_index,
                        content=piece.content, token_count=piece.token_count,
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
                await uow.document_chunk.delete_by_knowledge_file(kf.id, tenant_id)
                await uow.document_chunk.add_many(chunks_with_vectors)
                kf.status = FileStatus.INDEXED
                kf.chunk_count = len(chunks_with_vectors)
                kf.error_message = ""
                await uow.knowledge_file.save(kf)
            logger.info(f"政策收藏入库完成[{kf.id}]，共 {len(chunks_with_vectors)} 个切片")
        except Exception as e:
            error_detail = f"{type(e).__name__}: {str(e) or '未知错误'}"
            logger.exception(f"政策收藏入库失败[{kf.id}]: {error_detail}")
            kf.status = FileStatus.ERROR_INDEXING
            kf.error_message = error_detail[:1024]
            try:
                async with self._uow_factory() as uow:
                    await uow.knowledge_file.save(kf)
            except Exception:
                logger.exception(f"回写收藏文件[{kf.id}]失败状态时出错")

    # ---------- 入库流水线(后台执行) ----------

    async def ingest_file(self, knowledge_file_id: str, tenant_id: str) -> None:
        """解析→分块→向量化→落库，沿 FileStatus 状态机推进；失败置 error_* 并记录原因"""
        async with self._uow_factory() as uow:
            kf = await uow.knowledge_file.get_by_id(knowledge_file_id, tenant_id=tenant_id)
        if not kf:
            logger.warning(f"入库流水线找不到知识库文件[{knowledge_file_id}]，跳过")
            return

        stage = FileStatus.ERROR_PARSING  # 当前阶段失败时使用的错误态
        try:
            # 1. 解析
            await self._update_status(kf, FileStatus.PARSING)
            body, file = await self.file_storage.download_file(kf.file_id)
            content = await run_in_threadpool(body.read)
            pages = await self.parser.parse(content, file.extension)

            # 2. 分块
            pieces = chunk_pages(pages)
            await self._update_status(kf, FileStatus.PARSED)
            if not pieces:
                kf.chunk_count = 0
                await self._update_status(kf, FileStatus.INDEXED)
                logger.info(f"知识库文件[{kf.id}]无可索引文本，置为 indexed")
                return

            # 3. 向量化(进入 indexing 阶段，失败归类为 error_indexing)
            stage = FileStatus.ERROR_INDEXING
            await self._update_status(kf, FileStatus.INDEXING)
            vectors = await self.embedding.embed_documents([p.content for p in pieces])

            # 4. 落库(先清旧切片保证幂等，再批量写入 + 收尾)
            chunks_with_vectors = [
                (
                    DocumentChunk(
                        tenant_id=tenant_id, knowledge_base_id=kf.knowledge_base_id,
                        knowledge_file_id=kf.id, chunk_index=piece.chunk_index,
                        content=piece.content, token_count=piece.token_count,
                        chunk_metadata=piece.metadata,
                    ),
                    vector,
                )
                for piece, vector in zip(pieces, vectors)
            ]
            async with self._uow_factory() as uow:
                await uow.document_chunk.delete_by_knowledge_file(kf.id, tenant_id)
                await uow.document_chunk.add_many(chunks_with_vectors)
                kf.status = FileStatus.INDEXED
                kf.chunk_count = len(chunks_with_vectors)
                kf.error_message = ""
                await uow.knowledge_file.save(kf)
            logger.info(f"知识库文件[{kf.id}]入库完成，共 {len(chunks_with_vectors)} 个切片")
        except Exception as e:
            error_detail = f"{type(e).__name__}: {str(e) or '未知错误'}"
            logger.exception(f"知识库文件[{kf.id}]入库失败({stage.value}): {error_detail}")
            kf.status = stage
            kf.error_message = error_detail[:1024]
            try:
                async with self._uow_factory() as uow:
                    await uow.knowledge_file.save(kf)
            except Exception:
                logger.exception(f"回写知识库文件[{kf.id}]失败状态时出错")

    async def _update_status(self, kf: KnowledgeFile, status: FileStatus) -> None:
        """推进状态机并持久化(每次转换单独提交，便于前端轮询进度)"""
        kf.status = status
        async with self._uow_factory() as uow:
            await uow.knowledge_file.save(kf)
