from typing import Optional, Protocol

from app.domain.models.tenant_settings import TenantSettings


class TenantSettingsRepository(Protocol):
    """租户设置仓库协议定义"""

    async def get_by_tenant(self, tenant_id: str) -> Optional[TenantSettings]:
        """根据租户id查询租户设置"""
        ...

    async def save(self, settings: TenantSettings) -> None:
        """存储或更新租户设置"""
        ...
