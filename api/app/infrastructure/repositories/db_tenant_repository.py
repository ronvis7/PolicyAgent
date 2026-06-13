from typing import List, Optional

from sqlalchemy import func, select
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

    async def get_shared_by_name(self, name: str) -> Optional[Tenant]:
        """按规范化名称(忽略大小写与首尾空格)查询共享组织(非个人工作区)"""
        normalized = name.strip().lower()
        stmt = select(TenantModel).where(
            TenantModel.is_personal.is_(False),
            func.lower(func.trim(TenantModel.name)) == normalized,
        )
        result = await self.db_session.execute(stmt)
        record = result.scalars().first()
        return record.to_domain() if record is not None else None

    async def list_shared(self, query: str = "", limit: int = 20) -> List[Tenant]:
        """按名称模糊检索共享组织(供注册时选择加入)"""
        stmt = select(TenantModel).where(TenantModel.is_personal.is_(False))
        normalized = query.strip().lower()
        if normalized:
            stmt = stmt.where(func.lower(TenantModel.name).like(f"%{normalized}%"))
        stmt = stmt.order_by(TenantModel.created_at.asc()).limit(limit)
        result = await self.db_session.execute(stmt)
        return [record.to_domain() for record in result.scalars().all()]
