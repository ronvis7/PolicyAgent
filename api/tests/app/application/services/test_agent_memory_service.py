"""AgentMemoryService 单元测试（ADR 004 管理端）。

覆盖：按租户列出(倒序)、跨租户隔离不串、删除命中/未命中(跨租户)。用内存级 UoW 驱动。
"""
import asyncio
from datetime import datetime, timedelta

from app.application.services.agent_memory_service import AgentMemoryService
from app.domain.models.agent_memory import AgentMemory
from ._fakes import make_uow_factory

TENANT = "tenant-1"
OTHER = "tenant-2"


def _mem(mem_id: str, tenant_id: str, content: str, created_at: datetime) -> AgentMemory:
    return AgentMemory(id=mem_id, tenant_id=tenant_id, content=content, created_at=created_at)


def test_list_returns_tenant_memories_newest_first():
    """只列本租户记忆，按创建时间倒序。"""
    now = datetime.now()
    store = {
        "a": _mem("a", TENANT, "较早", now - timedelta(hours=1)),
        "b": _mem("b", TENANT, "较新", now),
        "c": _mem("c", OTHER, "他租户", now),
    }
    service = AgentMemoryService(uow_factory=make_uow_factory(agent_memories=store))

    items = asyncio.run(service.list_memories(TENANT))

    assert [m.content for m in items] == ["较新", "较早"]


def test_delete_hits_own_tenant():
    """删除本租户记忆命中返回 True 并真正移除。"""
    store = {"a": _mem("a", TENANT, "x", datetime.now())}
    service = AgentMemoryService(uow_factory=make_uow_factory(agent_memories=store))

    ok = asyncio.run(service.delete_memory(TENANT, "a"))

    assert ok is True
    assert "a" not in store


def test_delete_other_tenant_memory_misses():
    """删除他租户记忆未命中返回 False 且不影响数据(隔离)。"""
    store = {"a": _mem("a", OTHER, "x", datetime.now())}
    service = AgentMemoryService(uow_factory=make_uow_factory(agent_memories=store))

    ok = asyncio.run(service.delete_memory(TENANT, "a"))

    assert ok is False
    assert "a" in store
