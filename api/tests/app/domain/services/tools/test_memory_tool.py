"""MemoryTool 单元测试(跨会话记忆第 2 层 写入半边)。

覆盖：写入成功并落库、精确去重(同句不重复记)、空内容失败、超长截断、
无租户上下文失败、memory_list 空/有内容、跨租户隔离(只列本租户)。
用伪造 UoW 驱动，不依赖数据库；异步方法用 asyncio.run。
"""
import asyncio
from typing import Dict, List, Optional

from app.domain.models.agent_memory import AgentMemory
from app.domain.models.session import Session
from app.domain.services.tools.memory import MemoryTool, _MAX_CONTENT_LEN

TENANT = "tenant-1"
OWNER = "user-1"


class FakeSessionRepo:
    def __init__(self, tenant_id: Optional[str], owner_id: Optional[str] = OWNER) -> None:
        self._tenant_id = tenant_id
        self._owner_id = owner_id

    async def get_by_id(self, session_id: str):
        if self._tenant_id is None:
            return None
        return Session(id=session_id, tenant_id=self._tenant_id, owner_id=self._owner_id)


class FakeAgentMemoryRepo:
    """内存级长期记忆仓库，按租户过滤，按创建顺序倒序返回。"""

    def __init__(self, store: Dict[str, AgentMemory]) -> None:
        self._store = store

    async def list_by_tenant(self, tenant_id: str, limit: int = 0) -> List[AgentMemory]:
        items = [m for m in self._store.values() if m.tenant_id == tenant_id]
        items.sort(key=lambda m: m.created_at, reverse=True)
        return items[:limit] if limit and limit > 0 else items

    async def add(self, memory: AgentMemory) -> None:
        self._store[memory.id] = memory

    async def delete(self, tenant_id: str, memory_id: str) -> bool:
        item = self._store.get(memory_id)
        if item is None or item.tenant_id != tenant_id:
            return False
        del self._store[memory_id]
        return True


class FakeUoW:
    def __init__(self, session_repo, memory_repo) -> None:
        self.session = session_repo
        self.agent_memory = memory_repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _build_tool(tenant_id: Optional[str], store: Optional[Dict[str, AgentMemory]] = None):
    store = store if store is not None else {}
    uow = FakeUoW(FakeSessionRepo(tenant_id), FakeAgentMemoryRepo(store))
    tool = MemoryTool(uow_factory=lambda: uow, session_id="sess-1")
    return tool, store


def test_save_persists_memory_for_tenant():
    """写入成功：落库一条，归属当前租户与创建者。"""
    tool, store = _build_tool(TENANT)

    result = asyncio.run(tool.memory_save(content="该企业2026年新增3项发明专利"))

    assert result.success is True
    assert result.data.kind == "save"
    assert len(store) == 1
    saved = next(iter(store.values()))
    assert saved.tenant_id == TENANT
    assert saved.created_by == OWNER
    assert saved.source_session_id == "sess-1"
    assert saved.content == "该企业2026年新增3项发明专利"


def test_save_dedupes_exact_normalized_content():
    """精确去重：同一句(忽略空白/大小写)只记一次。"""
    tool, store = _build_tool(TENANT)

    asyncio.run(tool.memory_save(content="用户偏好简洁回答"))
    result = asyncio.run(tool.memory_save(content="  用户偏好简洁回答 "))

    assert result.success is True
    assert "无需重复" in result.message
    assert len(store) == 1


def test_save_empty_content_fails():
    """空内容写入失败。"""
    tool, _ = _build_tool(TENANT)
    result = asyncio.run(tool.memory_save(content="   "))
    assert result.success is False


def test_save_truncates_overlong_content():
    """超长内容被截断到上限。"""
    tool, store = _build_tool(TENANT)
    long_text = "专" * (_MAX_CONTENT_LEN + 50)

    result = asyncio.run(tool.memory_save(content=long_text))

    assert result.success is True
    saved = next(iter(store.values()))
    assert len(saved.content) == _MAX_CONTENT_LEN


def test_save_without_tenant_context_fails():
    """会话无租户上下文：写入失败、不落库。"""
    tool, store = _build_tool(None)
    result = asyncio.run(tool.memory_save(content="任意"))
    assert result.success is False
    assert len(store) == 0


def test_list_empty_returns_guidance():
    """无记忆时 list 成功返回但提示暂无。"""
    tool, _ = _build_tool(TENANT)
    result = asyncio.run(tool.memory_list())
    assert result.success is True
    assert result.data.kind == "list"
    assert result.data.lines == []


def test_list_only_returns_current_tenant_memories():
    """跨租户隔离：list 只返回本租户记忆。"""
    store = {
        "m1": AgentMemory(id="m1", tenant_id=TENANT, content="本租户记忆"),
        "m2": AgentMemory(id="m2", tenant_id="other-tenant", content="他租户记忆"),
    }
    tool, _ = _build_tool(TENANT, store)

    result = asyncio.run(tool.memory_list())

    assert result.success is True
    assert result.data.lines == ["本租户记忆"]
