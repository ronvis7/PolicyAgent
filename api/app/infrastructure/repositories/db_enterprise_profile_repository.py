from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.repositories.enterprise_profile_repository import EnterpriseProfileRepository
from app.infrastructure.models import EnterpriseProfileModel


class DBEnterpriseProfileRepository(EnterpriseProfileRepository):
    """基于Postgres数据库的企业档案仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_by_tenant(self, tenant_id: str) -> Optional[EnterpriseProfile]:
        """根据租户id查询企业档案"""
        stmt = select(EnterpriseProfileModel).where(EnterpriseProfileModel.tenant_id == tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def save(self, profile: EnterpriseProfile) -> None:
        """新增或更新企业档案"""
        # 1.按租户id查询是否已存在
        stmt = select(EnterpriseProfileModel).where(EnterpriseProfileModel.tenant_id == profile.tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.不存在则新建，存在则更新
        if not record:
            self.db_session.add(EnterpriseProfileModel.from_domain(profile))
            return
        record.update_from_domain(profile)

    async def list_tenant_ids(self) -> List[str]:
        """列出所有已建档租户id。"""
        stmt = select(EnterpriseProfileModel.tenant_id)
        result = await self.db_session.execute(stmt)
        return [row[0] for row in result.all()]
