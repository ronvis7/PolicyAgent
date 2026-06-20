from typing import List, Protocol

from app.domain.models.agent_memory import AgentMemory


class AgentMemoryRepository(Protocol):
    """Agent 长期记忆仓库协议定义（按租户隔离）。"""

    async def list_by_tenant(self, tenant_id: str, limit: int = 0) -> List[AgentMemory]:
        """按租户列出记忆条目，按创建时间倒序(最新在前)；limit<=0 表示不限制。"""
        ...

    async def add(self, memory: AgentMemory) -> None:
        """新增一条记忆。"""
        ...

    async def delete(self, tenant_id: str, memory_id: str) -> bool:
        """删除当前租户下指定记忆，返回是否命中删除(跨租户取不到→False)。"""
        ...
