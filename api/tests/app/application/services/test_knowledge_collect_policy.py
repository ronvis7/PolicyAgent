"""KnowledgeService 收藏公开政策入私有政策库的单元测试(ADR-003 阶段B)。

覆盖：库类型校验(只允许 policy 库)、政策存在性/空正文校验、收藏占位文件幂等 id，
以及后台向量化把政策正文切片落库。用伪造 UoW/embedding 驱动，不依赖数据库与向量服务。
"""
import asyncio
from typing import List, Optional

import pytest

from app.application.errors.exceptions import NotFoundError, ServerRequestsError
from app.application.services.knowledge_service import KnowledgeService
from app.domain.models.knowledge_base import KnowledgeBase, KnowledgeBaseType
from app.domain.models.knowledge_file import FileStatus, KnowledgeFile
from app.domain.models.policy import Policy

TENANT = "tenant-1"
OWNER = "user-1"


class FakeEmbedding:
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    @property
    def model_name(self) -> str:
        return "fake-embed"


class FakeKnowledgeBaseRepo:
    def __init__(self, kbs: List[KnowledgeBase]) -> None:
        self._kbs = kbs

    async def get_by_id(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBase]:
        for kb in self._kbs:
            if kb.id == kb_id and (tenant_id is None or kb.tenant_id == tenant_id):
                return kb
        return None


class FakePolicyRepo:
    def __init__(self, policies: dict) -> None:
        self._policies = policies

    async def get_by_id(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)


class FakeKnowledgeFileRepo:
    def __init__(self) -> None:
        self.saved: dict = {}

    async def save(self, kf: KnowledgeFile) -> None:
        self.saved[kf.id] = kf

    async def get_by_id(self, file_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeFile]:
        return self.saved.get(file_id)


class FakeChunkRepo:
    def __init__(self) -> None:
        self.deleted: List[str] = []
        self.added: List = []

    async def delete_by_knowledge_file(self, file_id: str, tenant_id: str) -> None:
        self.deleted.append(file_id)

    async def add_many(self, chunks_with_vectors: List) -> None:
        self.added.extend(chunks_with_vectors)


class FakeUoW:
    def __init__(self, kb_repo, policy_repo, file_repo, chunk_repo) -> None:
        self.knowledge_base = kb_repo
        self.policy = policy_repo
        self.knowledge_file = file_repo
        self.document_chunk = chunk_repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _build_service(kbs, policies, file_repo, chunk_repo) -> KnowledgeService:
    uow = FakeUoW(FakeKnowledgeBaseRepo(kbs), FakePolicyRepo(policies), file_repo, chunk_repo)
    return KnowledgeService(
        uow_factory=lambda: uow,
        file_storage=None,
        embedding=FakeEmbedding(),
        parser=None,
    )


def test_collect_policy_rejects_non_policy_kb():
    """收藏到 general 类型库被拒绝(只允许私有政策库)"""
    kbs = [KnowledgeBase(id="kb-gen", tenant_id=TENANT, type=KnowledgeBaseType.GENERAL)]
    policies = {"p1": Policy(id="p1", source_url="http://x/1", title="政策一", body_text="正文")}
    service = _build_service(kbs, policies, FakeKnowledgeFileRepo(), FakeChunkRepo())

    with pytest.raises(ServerRequestsError):
        asyncio.run(service.collect_policy("kb-gen", TENANT, OWNER, "p1"))


def test_collect_policy_missing_policy_raises():
    """政策不存在时抛 NotFound"""
    kbs = [KnowledgeBase(id="kb-pol", tenant_id=TENANT, type=KnowledgeBaseType.POLICY)]
    service = _build_service(kbs, {}, FakeKnowledgeFileRepo(), FakeChunkRepo())

    with pytest.raises(NotFoundError):
        asyncio.run(service.collect_policy("kb-pol", TENANT, OWNER, "missing"))


def test_collect_policy_empty_body_rejected():
    """政策无正文不可收藏"""
    kbs = [KnowledgeBase(id="kb-pol", tenant_id=TENANT, type=KnowledgeBaseType.POLICY)]
    policies = {"p1": Policy(id="p1", source_url="http://x/1", title="空", body_text="   ")}
    service = _build_service(kbs, policies, FakeKnowledgeFileRepo(), FakeChunkRepo())

    with pytest.raises(ServerRequestsError):
        asyncio.run(service.collect_policy("kb-pol", TENANT, OWNER, "p1"))


def test_collect_policy_creates_placeholder_idempotently():
    """收藏建占位文件(uploaded)，同政策重复收藏派生同一 file id(幂等)"""
    kbs = [KnowledgeBase(id="kb-pol", tenant_id=TENANT, type=KnowledgeBaseType.POLICY)]
    policies = {"p1": Policy(id="p1", source_url="http://x/1", title="政策一", body_text="正文内容")}
    file_repo = FakeKnowledgeFileRepo()
    service = _build_service(kbs, policies, file_repo, FakeChunkRepo())

    kf1 = asyncio.run(service.collect_policy("kb-pol", TENANT, OWNER, "p1"))
    kf2 = asyncio.run(service.collect_policy("kb-pol", TENANT, OWNER, "p1"))

    assert kf1.status == FileStatus.UPLOADED
    assert kf1.filename == "政策一"
    assert kf1.id == kf2.id  # 确定性 id，幂等
    assert len(file_repo.saved) == 1


def test_ingest_collected_policy_writes_chunks_with_tenant():
    """后台入库把政策正文切片向量化落库，挂当前租户并置 indexed"""
    kbs = [KnowledgeBase(id="kb-pol", tenant_id=TENANT, type=KnowledgeBaseType.POLICY)]
    policies = {"p1": Policy(id="p1", source_url="http://x/1", title="政策一", body_text="一段足够入库的政策正文内容")}
    file_repo = FakeKnowledgeFileRepo()
    chunk_repo = FakeChunkRepo()
    service = _build_service(kbs, policies, file_repo, chunk_repo)

    kf = asyncio.run(service.collect_policy("kb-pol", TENANT, OWNER, "p1"))
    asyncio.run(service.ingest_collected_policy(kf.id, TENANT, "p1"))

    saved = file_repo.saved[kf.id]
    assert saved.status == FileStatus.INDEXED
    assert saved.chunk_count == len(chunk_repo.added)
    assert chunk_repo.added, "应写入至少一个切片"
    chunk, _vector = chunk_repo.added[0]
    assert chunk.tenant_id == TENANT
    assert chunk.knowledge_base_id == "kb-pol"
    assert chunk.chunk_metadata["source_url"] == "http://x/1"
