from typing import Protocol, List, Optional

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

    async def get_shared_by_name(self, name: str) -> Optional[Tenant]:
        """按规范化名称(忽略大小写与首尾空格)查询共享组织(非个人工作区)"""
        ...

    async def list_shared(self, query: str = "", limit: int = 20) -> List[Tenant]:
        """按名称模糊检索共享组织(供注册时选择加入)"""
        ...
