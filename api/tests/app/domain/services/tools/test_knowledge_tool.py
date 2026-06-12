"""KnowledgeBaseTool 单元测试：跨库合并/排序、单库收窄、租户隔离与引用构建。

用伪造的 embedding 与 UoW(含各仓库)驱动，不依赖数据库与真实向量服务。
工具方法为异步，测试用 asyncio.run 驱动，避免依赖 pytest-asyncio 插件。
"""
import asyncio
from typing import List, Optional, Tuple

from app.domain.models.document_chunk import DocumentChunk
from app.domain.models.knowledge_base import KnowledgeBase
from app.domain.models.knowledge_file import KnowledgeFile
from app.domain.services.tools.knowledge import KnowledgeBaseTool

TENANT = "tenant-1"
OTHER_VECTOR = [0.1, 0.2, 0.3]


class FakeEmbedding:
    """固定向量的伪 embedding"""

    def __init__(self, vector: List[float]) -> None:
        self._v = vector

    async def embed_query(self, text: str) -> List[float]:
        return list(self._v)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [list(self._v) for _ in texts]

    @property
    def dimension(self) -> int:
        return len(self._v)

    @property
    def model_name(self) -> str:
        return "fake-embed"


class FakeSessionRepo:
    def __init__(self, tenant_id: Optional[str]) -> None:
        self._tenant_id = tenant_id

    async def get_by_id(self, session_id: str):
        if self._tenant_id is None:
            return None
        return KnowledgeBase(id=session_id, tenant_id=self._tenant_id)  # 仅需 .tenant_id


class FakeKnowledgeBaseRepo:
    def __init__(self, kbs: List[KnowledgeBase]) -> None:
        self._kbs = kbs

    async def list_by_tenant(self, tenant_id: str) -> List[KnowledgeBase]:
        return [kb for kb in self._kbs if kb.tenant_id == tenant_id]

    async def get_by_id(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBase]:
        for kb in self._kbs:
            if kb.id == kb_id and (tenant_id is None or kb.tenant_id == tenant_id):
                return kb
        return None


class FakeDocumentChunkRepo:
    def __init__(self, hits_by_kb: dict) -> None:
        self._hits_by_kb = hits_by_kb
        self.calls: List[Tuple[str, str, int]] = []  # (kb_id, tenant_id, top_k)

    async def search_similar(self, knowledge_base_id, tenant_id, query_embedding, top_k=5):
        self.calls.append((knowledge_base_id, tenant_id, top_k))
        return list(self._hits_by_kb.get(knowledge_base_id, []))


class FakeKnowledgeFileRepo:
    def __init__(self, files: dict) -> None:
        self._files = files  # file_id -> KnowledgeFile

    async def get_by_id(self, file_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeFile]:
        return self._files.get(file_id)


class FakeUoW:
    def __init__(self, session_repo, kb_repo, chunk_repo, file_repo) -> None:
        self.session = session_repo
        self.knowledge_base = kb_repo
        self.document_chunk = chunk_repo
        self.knowledge_file = file_repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _chunk(file_id: str, page: int, content: str, kb_id: str) -> DocumentChunk:
    return DocumentChunk(
        tenant_id=TENANT,
        knowledge_base_id=kb_id,
        knowledge_file_id=file_id,
        content=content,
        chunk_metadata={"page": page},
    )


def _build_tool(session_repo, kb_repo, chunk_repo, file_repo) -> KnowledgeBaseTool:
    uow = FakeUoW(session_repo, kb_repo, chunk_repo, file_repo)
    return KnowledgeBaseTool(
        uow_factory=lambda: uow,
        embedding=FakeEmbedding(OTHER_VECTOR),
        session_id="sess-1",
    )


def test_merges_and_ranks_across_all_tenant_kbs():
    """默认检索全部租户库，跨库合并后按相似度全局倒序并截断 top_k，且回查文件名/页码"""
    kbs = [
        KnowledgeBase(id="kb-a", tenant_id=TENANT),
        KnowledgeBase(id="kb-b", tenant_id=TENANT),
    ]
    chunk_repo = FakeDocumentChunkRepo({
        "kb-a": [(_chunk("f1", 3, "甲库切片", "kb-a"), 0.70)],
        "kb-b": [
            (_chunk("f2", 1, "乙库高分", "kb-b"), 0.95),
            (_chunk("f2", 2, "乙库低分", "kb-b"), 0.40),
        ],
    })
    file_repo = FakeKnowledgeFileRepo({
        "f1": KnowledgeFile(tenant_id=TENANT, knowledge_base_id="kb-a", filename="甲.pdf"),
        "f2": KnowledgeFile(tenant_id=TENANT, knowledge_base_id="kb-b", filename="乙.pdf"),
    })
    tool = _build_tool(FakeSessionRepo(TENANT), FakeKnowledgeBaseRepo(kbs), chunk_repo, file_repo)

    result = asyncio.run(tool.knowledge_base_search(query="查询", top_k=2))

    assert result.success is True
    citations = result.data.citations
    # 全局按 score 倒序，截断到 top_k=2
    assert [c.score for c in citations] == [0.95, 0.70]
    assert citations[0].filename == "乙.pdf" and citations[0].page == 1
    assert citations[1].filename == "甲.pdf" and citations[1].page == 3
    # 两个库都被检索，且都带上了正确的租户隔离条件
    searched_kbs = {kb for kb, _, _ in chunk_repo.calls}
    assert searched_kbs == {"kb-a", "kb-b"}
    assert all(tenant == TENANT for _, tenant, _ in chunk_repo.calls)


def test_scopes_to_single_kb_when_id_given():
    """指定 knowledge_base_id 时只检索该库(经租户归属校验)，不扫描其它库"""
    kbs = [
        KnowledgeBase(id="kb-a", tenant_id=TENANT),
        KnowledgeBase(id="kb-b", tenant_id=TENANT),
    ]
    chunk_repo = FakeDocumentChunkRepo({
        "kb-a": [(_chunk("f1", 1, "甲库", "kb-a"), 0.8)],
        "kb-b": [(_chunk("f2", 1, "乙库", "kb-b"), 0.9)],
    })
    file_repo = FakeKnowledgeFileRepo({
        "f1": KnowledgeFile(tenant_id=TENANT, knowledge_base_id="kb-a", filename="甲.pdf"),
    })
    tool = _build_tool(FakeSessionRepo(TENANT), FakeKnowledgeBaseRepo(kbs), chunk_repo, file_repo)

    result = asyncio.run(tool.knowledge_base_search(query="查询", knowledge_base_id="kb-a"))

    assert result.success is True
    assert [c.knowledge_base_id for c in result.data.citations] == ["kb-a"]
    assert {kb for kb, _, _ in chunk_repo.calls} == {"kb-a"}


def test_missing_tenant_returns_failure():
    """会话无租户上下文时返回失败，不进行检索"""
    chunk_repo = FakeDocumentChunkRepo({})
    tool = _build_tool(
        FakeSessionRepo(None), FakeKnowledgeBaseRepo([]), chunk_repo, FakeKnowledgeFileRepo({}),
    )

    result = asyncio.run(tool.knowledge_base_search(query="查询"))

    assert result.success is False
    assert chunk_repo.calls == []


def test_no_knowledge_base_returns_empty_success():
    """租户下无知识库时返回成功但引用为空"""
    chunk_repo = FakeDocumentChunkRepo({})
    tool = _build_tool(
        FakeSessionRepo(TENANT), FakeKnowledgeBaseRepo([]), chunk_repo, FakeKnowledgeFileRepo({}),
    )

    result = asyncio.run(tool.knowledge_base_search(query="查询"))

    assert result.success is True
    assert result.data.citations == []
    assert chunk_repo.calls == []


def test_blank_query_is_rejected():
    """空白查询直接拒绝"""
    chunk_repo = FakeDocumentChunkRepo({})
    tool = _build_tool(
        FakeSessionRepo(TENANT), FakeKnowledgeBaseRepo([]), chunk_repo, FakeKnowledgeFileRepo({}),
    )

    result = asyncio.run(tool.knowledge_base_search(query="   "))

    assert result.success is False
    assert chunk_repo.calls == []
