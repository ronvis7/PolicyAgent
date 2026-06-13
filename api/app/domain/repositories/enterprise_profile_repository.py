from typing import Optional, Protocol

from app.domain.models.enterprise_profile import EnterpriseProfile


class EnterpriseProfileRepository(Protocol):
    """企业档案仓库协议定义"""

    async def get_by_tenant(self, tenant_id: str) -> Optional[EnterpriseProfile]:
        """根据租户id查询企业档案"""
        ...

    async def save(self, profile: EnterpriseProfile) -> None:
        """存储或更新企业档案"""
        ...
