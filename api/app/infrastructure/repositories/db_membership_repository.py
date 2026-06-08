from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.membership import Membership
from app.domain.repositories.membership_repository import MembershipRepository
from app.infrastructure.models import MembershipModel


class DBMembershipRepository(MembershipRepository):
    """基于Postgres数据库的成员关系仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, membership: Membership) -> None:
        """新增或更新成员关系"""
        # 1.根据id查询成员关系是否存在
        stmt = select(MembershipModel).where(MembershipModel.id == membership.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.不存在则新建，存在则更新
        if not record:
            self.db_session.add(MembershipModel.from_domain(membership))
            return
        record.update_from_domain(membership)

    async def get_by_user_and_tenant(self, user_id: str, tenant_id: str) -> Optional[Membership]:
        """根据用户id+租户id查询成员关系"""
        stmt = select(MembershipModel).where(
            MembershipModel.user_id == user_id,
            MembershipModel.tenant_id == tenant_id,
        )
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def list_by_user(self, user_id: str) -> List[Membership]:
        """查询某用户的所有成员关系"""
        stmt = (
            select(MembershipModel)
            .where(MembershipModel.user_id == user_id)
            .order_by(MembershipModel.created_at.asc())
        )
        result = await self.db_session.execute(stmt)
        return [record.to_domain() for record in result.scalars().all()]

    async def list_by_tenant(self, tenant_id: str) -> List[Membership]:
        """查询某租户下的所有成员关系"""
        stmt = (
            select(MembershipModel)
            .where(MembershipModel.tenant_id == tenant_id)
            .order_by(MembershipModel.created_at.asc())
        )
        result = await self.db_session.execute(stmt)
        return [record.to_domain() for record in result.scalars().all()]
