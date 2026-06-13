from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.tenant_settings import TenantSettings
from app.domain.repositories.tenant_settings_repository import TenantSettingsRepository
from app.infrastructure.models import TenantSettingsModel


class DBTenantSettingsRepository(TenantSettingsRepository):
    """基于Postgres数据库的租户设置仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_by_tenant(self, tenant_id: str) -> Optional[TenantSettings]:
        """根据租户id查询租户设置"""
        stmt = select(TenantSettingsModel).where(TenantSettingsModel.tenant_id == tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def save(self, settings: TenantSettings) -> None:
        """新增或更新租户设置"""
        # 1.按租户id查询是否已存在
        stmt = select(TenantSettingsModel).where(TenantSettingsModel.tenant_id == settings.tenant_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.不存在则新建，存在则更新
        if not record:
            self.db_session.add(TenantSettingsModel.from_domain(settings))
            return
        record.update_from_domain(settings)
