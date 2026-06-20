"""Agent 长期记忆管理服务：按租户列出/删除记忆条目（ADR 004）。

读侧给前端「Agent 记忆」页提供"Agent 记住了什么"的可见性；删侧让用户清理记忆。
写入由 Agent 在对话中通过 MemoryTool 自主完成，本服务不负责写入。
"""

import logging
from typing import Callable, List

from app.domain.models.agent_memory import AgentMemory
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """Agent 长期记忆管理服务，按租户读/删（隔离边界为 tenant_id）。"""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def list_memories(self, tenant_id: str) -> List[AgentMemory]:
        """列出某租户的全部长期记忆，按创建时间倒序(最新在前)。"""
        async with self.uow_factory() as uow:
            return await uow.agent_memory.list_by_tenant(tenant_id)

    async def delete_memory(self, tenant_id: str, memory_id: str) -> bool:
        """删除当前租户下指定记忆，返回是否命中(跨租户取不到→False)。"""
        async with self.uow_factory() as uow:
            return await uow.agent_memory.delete(tenant_id, memory_id)
