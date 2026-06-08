from typing import Protocol, Optional

from app.domain.models.tenant import Tenant


class TenantRepository(Protocol):
    """租户仓库协议定义"""

    async def save(self, tenant: Tenant) -> None:
        """存储或更新租户"""
        ...

    async def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """根据租户id查询租户"""
        ...

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """根据slug查询租户"""
        ...
