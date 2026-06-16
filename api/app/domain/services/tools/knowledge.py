import logging
from typing import Callable, List, Optional, Tuple

from app.domain.external.embedding import EmbeddingProvider
from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.knowledge_search import KnowledgeCitation, KnowledgeSearchResults
from app.domain.models.tool_result import ToolResult
from app.domain.repositories.uow import IUnitOfWork
from .base import BaseTool, tool

logger = logging.getLogger(__name__)

# top_k 取值边界，防止 LLM 幻觉给出过大/非法值拖垮检索
MIN_TOP_K = 1
MAX_TOP_K = 20
DEFAULT_TOP_K = 5


class KnowledgeBaseTool(BaseTool):
    """知识库检索工具(agentic RAG，见 ADR-002)

    将查询向量化后做相似检索，返回带引用元数据(文件名/页码/相似度)的切片，供 Agent
    生成「带引用的回答」。默认检索范围 = 当前会话租户的全部私有知识库 + 全局公开库
    (is_public，如主线②爬取入库的公开政策库)；私有库按会话懒加载的租户隔离，公开库
    跨租户共享。可用 knowledge_base_id 收窄到单库；会话若绑定了某库则硬限定到该库
    (覆盖默认范围，不再附加公开库)。
    """
    name: str = "knowledge"

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        embedding: EmbeddingProvider,
        session_id: str,
    ) -> None:
        """构造函数，完成知识库检索工具初始化"""
        super().__init__()
        self._uow_factory = uow_factory
        self._embedding = embedding
        self._session_id = session_id
        # 会话范围懒加载缓存：租户id(隔离边界) + 绑定知识库id(检索硬限定范围)
        self._tenant_id: Optional[str] = None
        self._bound_kb_id: Optional[str] = None
        self._scope_loaded = False

    async def _load_scope(self) -> None:
        """懒加载当前会话的租户id与绑定知识库id，作为检索的范围边界"""
        if not self._scope_loaded:
            async with self._uow_factory() as uow:
                session = await uow.session.get_by_id(self._session_id)
            self._tenant_id = session.tenant_id if session else None
            self._bound_kb_id = session.knowledge_base_id if session else None
            self._scope_loaded = True

    async def _get_tenant_id(self) -> Optional[str]:
        """懒加载并返回当前会话所属租户id，作为检索的租户隔离边界"""
        await self._load_scope()
        return self._tenant_id

    @tool(
        name="knowledge_base_search",
        description=(
            "政策知识库语义检索工具，覆盖本企业(租户)私有知识库 + 全局公开政策库"
            "(主线②爬取入库的公开政策文件)。当用户咨询政策、法规、办事流程、申报条件、"
            "补贴/资质要求等知识库可能涵盖的问题时，应优先调用本工具检索，并基于返回的"
            "切片作答，回答中需注明来源(文件名与页码)。返回的每条结果包含命中文本及其来源"
            "文件名、页码与相似度。若本工具无相关结果，再考虑使用 search_web。"
        ),
        parameters={
            "query": {
                "type": "string",
                "description": "检索查询。请提炼用户问题中的核心政策概念与关键词(如'研发费用加计扣除 比例')，而非整句自然语言。",
            },
            "knowledge_base_id": {
                "type": "string",
                "description": "(可选)将检索范围收窄到指定知识库id。默认检索当前租户下的全部知识库。",
            },
            "top_k": {
                "type": "integer",
                "description": "(可选)返回的最相关切片数量，默认 5，取值范围 1-20。",
            },
        },
        required=["query"],
    )
    async def knowledge_base_search(
        self,
        query: str,
        knowledge_base_id: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> ToolResult[KnowledgeSearchResults]:
        """向量化查询并在租户知识库内相似检索，返回带引用的切片"""
        # 1. 校验查询与租户上下文
        query = (query or "").strip()
        if not query:
            return ToolResult(success=False, message="检索查询不能为空")

        tenant_id = await self._get_tenant_id()
        if not tenant_id:
            return ToolResult(success=False, message="当前会话缺少租户上下文，无法检索知识库")

        # 1.5 会话绑定库为硬限定：存在时忽略 LLM 传入的 knowledge_base_id，
        #     确保用户在会话级选定的范围不被 Agent 绕过(见 ADR-002 scope 选择器)
        if self._bound_kb_id:
            knowledge_base_id = self._bound_kb_id

        # 2. 规整 top_k 到合法区间
        top_k = max(MIN_TOP_K, min(MAX_TOP_K, top_k or DEFAULT_TOP_K))

        # 3. 查询向量化
        query_embedding = await self._embedding.embed_query(query)
        if not query_embedding:
            return ToolResult(success=False, message="查询向量化失败，无法检索")

        # 4. 解析检索范围(私有库挂会话租户 + 公开库挂各自系统租户)，逐库检索并合并
        async with self._uow_factory() as uow:
            scopes = await self._resolve_kb_scopes(uow, tenant_id, knowledge_base_id)
            if not scopes:
                return ToolResult(
                    success=True,
                    message="当前暂无可检索的知识库",
                    data=KnowledgeSearchResults(query=query, citations=[]),
                )

            scored: List[Tuple[DocumentChunk, float]] = []
            for kb_id, kb_tenant_id in scopes:
                hits = await uow.document_chunk.search_similar(
                    knowledge_base_id=kb_id,
                    tenant_id=kb_tenant_id,
                    query_embedding=query_embedding,
                    top_k=top_k,
                )
                scored.extend(hits)

            # 5. 跨库合并后按相似度全局排序，截取 top_k
            scored.sort(key=lambda pair: pair[1], reverse=True)
            scored = scored[:top_k]

            # 6. 回查文件名(按 切片自带的租户 隔离查询)并构建引用
            citations = await self._build_citations(uow, scored)

        results = KnowledgeSearchResults(query=query, citations=citations)
        if not citations:
            return ToolResult(
                success=True,
                message="知识库中未检索到与查询相关的内容",
                data=results,
            )
        return ToolResult(
            success=True,
            message=f"命中 {len(citations)} 条相关切片",
            data=results,
        )

    @staticmethod
    async def _resolve_kb_scopes(
        uow: IUnitOfWork, tenant_id: str, knowledge_base_id: Optional[str],
    ) -> List[Tuple[str, str]]:
        """确定检索范围，返回 (知识库id, 该库所属租户id) 列表。

        - 指定 knowledge_base_id：先按会话租户校验私有归属，未命中再尝试公开库；
          (会话绑定库已在调用前赋给 knowledge_base_id，故绑定时只命中单库、不附加公开库。)
        - 未指定(默认)：会话租户全部私有库(挂会话租户) + 全部公开库(挂各自系统租户)。
        """
        if knowledge_base_id:
            kb = await uow.knowledge_base.get_by_id(knowledge_base_id, tenant_id=tenant_id)
            if kb:
                return [(kb.id, tenant_id)]
            public = await uow.knowledge_base.get_by_id(knowledge_base_id)
            if public and public.is_public:
                return [(public.id, public.tenant_id)]
            return []

        scopes: List[Tuple[str, str]] = [
            (kb.id, tenant_id) for kb in await uow.knowledge_base.list_by_tenant(tenant_id)
        ]
        seen = {kb_id for kb_id, _ in scopes}
        for kb in await uow.knowledge_base.list_public():
            if kb.id not in seen:  # 避免会话租户恰为系统公开租户时重复
                scopes.append((kb.id, kb.tenant_id))
        return scopes

    @staticmethod
    async def _build_citations(
        uow: IUnitOfWork, scored: List[Tuple[DocumentChunk, float]],
    ) -> List[KnowledgeCitation]:
        """将(切片, 相似度)列表转换为引用，回查文件名(按 租户+文件id 去重缓存)。

        每个切片自带 tenant_id(私有库=会话租户，公开库=系统租户)，按其各自租户回查文件，
        保证跨私有/公开库混合检索时来源归属正确。
        """
        filename_cache: dict = {}
        citations: List[KnowledgeCitation] = []
        for chunk, score in scored:
            cache_key = (chunk.tenant_id, chunk.knowledge_file_id)
            if cache_key not in filename_cache:
                kf = await uow.knowledge_file.get_by_id(
                    chunk.knowledge_file_id, tenant_id=chunk.tenant_id,
                )
                filename_cache[cache_key] = kf.filename if kf else ""
            citations.append(
                KnowledgeCitation(
                    chunk_id=chunk.id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    knowledge_file_id=chunk.knowledge_file_id,
                    filename=filename_cache[cache_key],
                    page=chunk.chunk_metadata.get("page") if chunk.chunk_metadata else None,
                    content=chunk.content,
                    score=score,
                )
            )
        return citations
