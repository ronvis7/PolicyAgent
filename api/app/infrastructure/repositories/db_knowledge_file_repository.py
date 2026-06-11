from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.knowledge_file import KnowledgeFile
from app.domain.repositories.knowledge_file_repository import KnowledgeFileRepository
from app.infrastructure.models import KnowledgeFileModel


class DBKnowledgeFileRepository(KnowledgeFileRepository):
    """基于Postgres数据库的知识库文件仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, knowledge_file: KnowledgeFile) -> None:
        """新增或更新知识库文件"""
        stmt = select(KnowledgeFileModel).where(KnowledgeFileModel.id == knowledge_file.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            self.db_session.add(KnowledgeFileModel.from_domain(knowledge_file))
            return
        record.update_from_domain(knowledge_file)

    async def get_by_id(self, file_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeFile]:
        """根据id获取知识库文件(传入tenant_id则要求归属该租户)"""
        stmt = select(KnowledgeFileModel).where(KnowledgeFileModel.id == file_id)
        if tenant_id is not None:
            stmt = stmt.where(KnowledgeFileModel.tenant_id == tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def list_by_knowledge_base(self, kb_id: str, tenant_id: str) -> List[KnowledgeFile]:
        """列出某知识库下的全部文件(按创建时间倒序，要求归属该租户)"""
        stmt = (
            select(KnowledgeFileModel)
            .where(
                KnowledgeFileModel.knowledge_base_id == kb_id,
                KnowledgeFileModel.tenant_id == tenant_id,
            )
            .order_by(KnowledgeFileModel.created_at.desc())
        )
        result = await self.db_session.execute(stmt)
        return [record.to_domain() for record in result.scalars().all()]

    async def delete(self, file_id: str, tenant_id: str) -> None:
        """删除知识库文件(级联删除其切片，要求归属该租户)"""
        stmt = delete(KnowledgeFileModel).where(
            KnowledgeFileModel.id == file_id,
            KnowledgeFileModel.tenant_id == tenant_id,
        )
        await self.db_session.execute(stmt)
