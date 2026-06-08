from typing import Protocol, List, Optional

from app.domain.models.membership import Membership


class MembershipRepository(Protocol):
    """成员关系仓库协议定义"""

    async def save(self, membership: Membership) -> None:
        """存储或更新成员关系"""
        ...

    async def get_by_user_and_tenant(self, user_id: str, tenant_id: str) -> Optional[Membership]:
        """根据用户id+租户id查询成员关系"""
        ...

    async def list_by_user(self, user_id: str) -> List[Membership]:
        """查询某用户的所有成员关系"""
        ...

    async def list_by_tenant(self, tenant_id: str) -> List[Membership]:
        """查询某租户下的所有成员关系"""
        ...
