from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.tenant import Tenant
from app.domain.repositories.tenant_repository import TenantRepository
from app.infrastructure.models import TenantModel


class DBTenantRepository(TenantRepository):
    """基于Postgres数据库的租户仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, tenant: Tenant) -> None:
        """新增或更新租户"""
        # 1.根据id查询租户是否存在
        stmt = select(TenantModel).where(TenantModel.id == tenant.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.不存在则新建，存在则更新
        if not record:
            self.db_session.add(TenantModel.from_domain(tenant))
            return
        record.update_from_domain(tenant)

    async def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """根据租户id查询租户"""
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """根据slug查询租户"""
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None
