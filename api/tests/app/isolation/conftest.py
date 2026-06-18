"""跨租户隔离 endpoint 测试基建（离线，进 CI）。

忠实自动化 `scripts/cross-tenant-probe.ps1`：用 FastAPI TestClient 打真实端点 →
真实服务 → 内存仓储（按 tenant_id 过滤，镜像真实 SQL 的 WHERE）。

- 不触发 lifespan（`TestClient(app)` 不进上下文管理器即不连库/Redis/COS）。
- 覆盖 `get_token_service`（假 token→claims，使真实 `get_current_user` 仍跑，
  覆盖"无 token→401"）+ 各 service provider（接同一共享内存 UoW，含 A/B 两租户数据）。
- 内存仓储测的是"端点/服务是否用 current_user.tenant_id 作用域"这一层回归；
  仓储 SQL 层 WHERE 回归需 DB-in-CI 集成测试（见 handoff 后续项）。
"""
from io import BytesIO
from typing import Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.application.errors.exceptions import UnauthorizedError
from app.application.services.enterprise_profile_service import EnterpriseProfileService
from app.application.services.feed_service import FeedService
from app.application.services.file_service import FileService
from app.application.services.knowledge_service import KnowledgeService
from app.application.services.session_service import SessionService
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedStatus
from app.domain.models.file import File
from app.domain.models.knowledge_base import KnowledgeBase, KnowledgeBaseType
from app.domain.models.session import Session
from app.interfaces import auth_dependencies as auth_deps
from app.interfaces import service_dependencies as deps
from app.main import app

TENANT_A, USER_A, TOKEN_A = "tenant-a", "user-a", "tok-a"
TENANT_B, USER_B, TOKEN_B = "tenant-b", "user-b", "tok-b"


# ---------- 内存仓储（按 tenant_id 过滤，镜像真实 SQL 隔离条件）----------

class _SessionRepo:
    def __init__(self, rows: List[Session]) -> None:
        self._rows = {s.id: s for s in rows}

    async def save(self, session: Session) -> None:
        self._rows[session.id] = session

    async def get_by_id(self, session_id: str, tenant_id: Optional[str] = None) -> Optional[Session]:
        s = self._rows.get(session_id)
        if s and (tenant_id is None or s.tenant_id == tenant_id):
            return s
        return None

    async def get_all(self, tenant_id: str) -> List[Session]:
        return [s for s in self._rows.values() if s.tenant_id == tenant_id]

    async def delete_by_id(self, session_id: str, tenant_id: str) -> None:
        s = self._rows.get(session_id)
        if s and s.tenant_id == tenant_id:
            del self._rows[session_id]


class _KnowledgeBaseRepo:
    def __init__(self, rows: List[KnowledgeBase]) -> None:
        self._rows = {kb.id: kb for kb in rows}

    async def get_by_id(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBase]:
        kb = self._rows.get(kb_id)
        if kb and (tenant_id is None or kb.tenant_id == tenant_id):
            return kb
        return None

    async def list_by_tenant(self, tenant_id: str) -> List[KnowledgeBase]:
        return [kb for kb in self._rows.values() if kb.tenant_id == tenant_id]

    async def save(self, kb: KnowledgeBase) -> None:
        self._rows[kb.id] = kb

    async def delete(self, kb_id: str, tenant_id: str) -> None:
        kb = self._rows.get(kb_id)
        if kb and kb.tenant_id == tenant_id:
            del self._rows[kb_id]


class _EnterpriseProfileRepo:
    def __init__(self, rows: List[EnterpriseProfile]) -> None:
        self._rows = {p.tenant_id: p for p in rows}

    async def get_by_tenant(self, tenant_id: str) -> Optional[EnterpriseProfile]:
        return self._rows.get(tenant_id)

    async def save(self, profile: EnterpriseProfile) -> None:
        self._rows[profile.tenant_id] = profile


class _FeedRepo:
    def __init__(self, rows: List[FeedItem]) -> None:
        self._rows = {i.id: i for i in rows}

    async def get_by_id(self, tenant_id: str, item_id: str) -> Optional[FeedItem]:
        item = self._rows.get(item_id)
        if item and item.tenant_id == tenant_id:
            return item
        return None

    async def save(self, item: FeedItem) -> None:
        self._rows[item.id] = item


class _FileRepo:
    def __init__(self, rows: List[File]) -> None:
        self._rows = {f.id: f for f in rows}

    async def get_by_id(self, file_id: str, tenant_id: Optional[str] = None) -> Optional[File]:
        f = self._rows.get(file_id)
        if f and (tenant_id is None or f.tenant_id == tenant_id):
            return f
        return None


class _InMemoryUoW:
    """共享内存 UoW，可重复 `async with`（SessionService/FileService 构造时建一次反复复用）。"""

    def __init__(self) -> None:
        self.session = _SessionRepo([
            Session(id="sess-a", tenant_id=TENANT_A, owner_id=USER_A, title="A 的会话"),
            Session(id="sess-b", tenant_id=TENANT_B, owner_id=USER_B, title="B 的会话"),
        ])
        self.knowledge_base = _KnowledgeBaseRepo([
            KnowledgeBase(id="kb-a", tenant_id=TENANT_A, name="A 库", type=KnowledgeBaseType.GENERAL),
            KnowledgeBase(id="kb-b", tenant_id=TENANT_B, name="B 库", type=KnowledgeBaseType.GENERAL),
        ])
        self.enterprise_profile = _EnterpriseProfileRepo([
            EnterpriseProfile(tenant_id=TENANT_A, company_name="A 公司"),
            EnterpriseProfile(tenant_id=TENANT_B, company_name="B 公司"),
        ])
        self.feed = _FeedRepo([
            FeedItem(id="feed-a", tenant_id=TENANT_A, policy_id="pa", title="A 机会"),
            FeedItem(id="feed-b", tenant_id=TENANT_B, policy_id="pb", title="B 机会"),
        ])
        self.file = _FileRepo([
            File(id="file-a", tenant_id=TENANT_A, filename="a.txt", mime_type="text/plain", size=4),
            File(id="file-b", tenant_id=TENANT_B, filename="b.txt", mime_type="text/plain", size=4),
        ])

    async def __aenter__(self) -> "_InMemoryUoW":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    async def commit(self) -> None:
        ...

    async def flush(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class _FakeTokenService:
    """假令牌服务：已知 token → access claims；未知 → 401（镜像真实解码失败）。"""

    def __init__(self, mapping: Dict[str, dict]) -> None:
        self._mapping = mapping

    def decode(self, token: str) -> dict:
        claims = self._mapping.get(token)
        if claims is None:
            raise UnauthorizedError("无效的访问令牌")
        return claims


class _FakeFileStorage:
    """假文件存储：下载返回固定字节流 + 文件信息（隔离测试只需正向控制能取到内容）。"""

    async def download_file(self, file_id: str):
        info = File(id=file_id, filename="a.txt", mime_type="text/plain", size=4)
        return BytesIO(b"data"), info


class _DummySandbox:
    """占位沙箱类（会话删除/读不触达沙箱；仅满足 SessionService 构造签名）。"""


@pytest.fixture()
def uow() -> _InMemoryUoW:
    """每个用例一份全新内存 UoW（含 A/B 两租户数据），避免用例间互相污染。"""
    return _InMemoryUoW()


@pytest.fixture()
def client(uow: _InMemoryUoW) -> TestClient:
    """TestClient（不进 lifespan）+ 覆盖令牌服务与各 service provider 接入内存 UoW。"""
    token_service = _FakeTokenService({
        TOKEN_A: {"sub": USER_A, "tid": TENANT_A, "role": "owner", "type": "access"},
        TOKEN_B: {"sub": USER_B, "tid": TENANT_B, "role": "owner", "type": "access"},
    })

    overrides = {
        deps.get_token_service: lambda: token_service,
        deps.get_session_service: lambda: SessionService(uow_factory=lambda: uow, sandbox_cls=_DummySandbox),
        deps.get_knowledge_service: lambda: KnowledgeService(
            uow_factory=lambda: uow, file_storage=None, embedding=None, parser=None,
        ),
        deps.get_enterprise_profile_service: lambda: EnterpriseProfileService(uow_factory=lambda: uow),
        deps.get_feed_service: lambda: FeedService(
            uow_factory=lambda: uow, match_service=None, qualification_service=None,
        ),
        deps.get_file_service: lambda: FileService(
            uow_factory=lambda: uow, file_storage=_FakeFileStorage(),
        ),
    }
    app.dependency_overrides.update(overrides)
    try:
        yield TestClient(app)
    finally:
        for key in overrides:
            app.dependency_overrides.pop(key, None)


def auth(token: str) -> dict:
    """构造 Authorization 头"""
    return {"Authorization": f"Bearer {token}"}
