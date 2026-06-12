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

    将查询向量化后在当前会话租户的知识库内做相似检索，返回带引用元数据
    (文件名/页码/相似度)的切片，供 Agent 生成「带引用的回答」。租户范围由会话
    懒加载得到，确保多租户隔离；默认检索该租户全部知识库，可用 knowledge_base_id
    收窄到单库。
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
        # 会话租户懒加载缓存(检索范围边界)
        self._tenant_id: Optional[str] = None
        self._scope_loaded = False

    async def _get_tenant_id(self) -> Optional[str]:
        """懒加载当前会话所属租户id，作为检索的租户隔离边界"""
        if not self._scope_loaded:
            async with self._uow_factory() as uow:
                session = await uow.session.get_by_id(self._session_id)
            self._tenant_id = session.tenant_id if session else None
            self._scope_loaded = True
        return self._tenant_id

    @tool(
        name="knowledge_base_search",
        description=(
            "内部政策知识库语义检索工具。当用户咨询政策、法规、办事流程、申报条件、"
            "补贴/资质要求等内部知识库可能涵盖的问题时，应优先调用本工具检索，并基于"
            "返回的切片作答，回答中需注明来源(文件名与页码)。返回的每条结果包含命中"
            "文本及其来源文件名、页码与相似度。若本工具无相关结果，再考虑使用 search_web。"
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

        # 2. 规整 top_k 到合法区间
        top_k = max(MIN_TOP_K, min(MAX_TOP_K, top_k or DEFAULT_TOP_K))

        # 3. 查询向量化
        query_embedding = await self._embedding.embed_query(query)
        if not query_embedding:
            return ToolResult(success=False, message="查询向量化失败，无法检索")

        # 4. 在租户范围内逐库检索并合并(默认全部库，或收窄到指定库)
        async with self._uow_factory() as uow:
            kb_ids = await self._resolve_kb_ids(uow, tenant_id, knowledge_base_id)
            if not kb_ids:
                return ToolResult(
                    success=True,
                    message="当前租户暂无可检索的知识库",
                    data=KnowledgeSearchResults(query=query, citations=[]),
                )

            scored: List[Tuple[DocumentChunk, float]] = []
            for kb_id in kb_ids:
                hits = await uow.document_chunk.search_similar(
                    knowledge_base_id=kb_id,
                    tenant_id=tenant_id,
                    query_embedding=query_embedding,
                    top_k=top_k,
                )
                scored.extend(hits)

            # 5. 跨库合并后按相似度全局排序，截取 top_k
            scored.sort(key=lambda pair: pair[1], reverse=True)
            scored = scored[:top_k]

            # 6. 回查文件名(批量去重)并构建引用
            citations = await self._build_citations(uow, tenant_id, scored)

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
    async def _resolve_kb_ids(
        uow: IUnitOfWork, tenant_id: str, knowledge_base_id: Optional[str],
    ) -> List[str]:
        """确定检索的知识库id集合：指定则校验归属，否则取该租户全部"""
        if knowledge_base_id:
            kb = await uow.knowledge_base.get_by_id(knowledge_base_id, tenant_id=tenant_id)
            return [kb.id] if kb else []
        kbs = await uow.knowledge_base.list_by_tenant(tenant_id)
        return [kb.id for kb in kbs]

    @staticmethod
    async def _build_citations(
        uow: IUnitOfWork, tenant_id: str, scored: List[Tuple[DocumentChunk, float]],
    ) -> List[KnowledgeCitation]:
        """将(切片, 相似度)列表转换为引用，回查文件名(按文件id去重缓存)"""
        filename_cache: dict = {}
        citations: List[KnowledgeCitation] = []
        for chunk, score in scored:
            if chunk.knowledge_file_id not in filename_cache:
                kf = await uow.knowledge_file.get_by_id(chunk.knowledge_file_id, tenant_id=tenant_id)
                filename_cache[chunk.knowledge_file_id] = kf.filename if kf else ""
            citations.append(
                KnowledgeCitation(
                    chunk_id=chunk.id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    knowledge_file_id=chunk.knowledge_file_id,
                    filename=filename_cache[chunk.knowledge_file_id],
                    page=chunk.chunk_metadata.get("page") if chunk.chunk_metadata else None,
                    content=chunk.content,
                    score=score,
                )
            )
        return citations
