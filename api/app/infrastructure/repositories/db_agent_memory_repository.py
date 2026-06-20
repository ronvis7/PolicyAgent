from typing import List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.agent_memory import AgentMemory
from app.domain.repositories.agent_memory_repository import AgentMemoryRepository
from app.infrastructure.models import AgentMemoryModel


class DBAgentMemoryRepository(AgentMemoryRepository):
    """基于 Postgres 数据库的 Agent 长期记忆仓库（按租户隔离）。"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def list_by_tenant(self, tenant_id: str, limit: int = 0) -> List[AgentMemory]:
        """按租户列出记忆，按创建时间倒序(最新在前)；limit<=0 不限制。"""
        stmt = (
            select(AgentMemoryModel)
            .where(AgentMemoryModel.tenant_id == tenant_id)
            .order_by(AgentMemoryModel.created_at.desc())
        )
        if limit and limit > 0:
            stmt = stmt.limit(limit)
        records = (await self.db_session.execute(stmt)).scalars().all()
        return [r.to_domain() for r in records]

    async def add(self, memory: AgentMemory) -> None:
        """新增一条记忆。"""
        self.db_session.add(AgentMemoryModel.from_domain(memory))

    async def delete(self, tenant_id: str, memory_id: str) -> bool:
        """删除当前租户下指定记忆，返回是否命中(跨租户取不到→False)。"""
        stmt = delete(AgentMemoryModel).where(
            AgentMemoryModel.id == memory_id,
            AgentMemoryModel.tenant_id == tenant_id,
        )
        result = await self.db_session.execute(stmt)
        return result.rowcount > 0
