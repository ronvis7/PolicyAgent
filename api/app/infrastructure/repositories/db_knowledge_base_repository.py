from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.knowledge_base import KnowledgeBase
from app.domain.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.infrastructure.models import KnowledgeBaseModel


class DBKnowledgeBaseRepository(KnowledgeBaseRepository):
    """基于Postgres数据库的知识库仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, knowledge_base: KnowledgeBase) -> None:
        """新增或更新知识库"""
        stmt = select(KnowledgeBaseModel).where(KnowledgeBaseModel.id == knowledge_base.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            self.db_session.add(KnowledgeBaseModel.from_domain(knowledge_base))
            return
        record.update_from_domain(knowledge_base)

    async def get_by_id(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBase]:
        """根据id获取知识库(传入tenant_id则要求归属该租户)"""
        stmt = select(KnowledgeBaseModel).where(KnowledgeBaseModel.id == kb_id)
        if tenant_id is not None:
            stmt = stmt.where(KnowledgeBaseModel.tenant_id == tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def list_by_tenant(self, tenant_id: str) -> List[KnowledgeBase]:
        """列出某租户下的全部知识库(按创建时间倒序)"""
        stmt = (
            select(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.tenant_id == tenant_id)
            .order_by(KnowledgeBaseModel.created_at.desc())
        )
        result = await self.db_session.execute(stmt)
        return [record.to_domain() for record in result.scalars().all()]

    async def list_public(self) -> List[KnowledgeBase]:
        """列出全部全局公开库(is_public=True，跨租户共享，按创建时间倒序)"""
        stmt = (
            select(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.is_public.is_(True))
            .order_by(KnowledgeBaseModel.created_at.desc())
        )
        result = await self.db_session.execute(stmt)
        return [record.to_domain() for record in result.scalars().all()]

    async def delete(self, kb_id: str, tenant_id: str) -> None:
        """删除知识库(级联删除其文件与切片，要求归属该租户)"""
        stmt = delete(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == kb_id,
            KnowledgeBaseModel.tenant_id == tenant_id,
        )
        await self.db_session.execute(stmt)
