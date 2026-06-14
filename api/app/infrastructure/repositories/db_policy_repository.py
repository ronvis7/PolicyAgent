from typing import List, Optional, Tuple

from sqlalchemy import func, select

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.policy import Policy
from app.domain.repositories.policy_repository import PolicyRepository
from app.infrastructure.models import PolicyModel


class DBPolicyRepository(PolicyRepository):
    """基于Postgres数据库的公开政策仓库（全局共享）"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_by_id(self, policy_id: str) -> Optional[Policy]:
        """按政策id查询"""
        stmt = select(PolicyModel).where(PolicyModel.id == policy_id)
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def get_by_source_url(self, source_url: str) -> Optional[Policy]:
        """按详情页URL查询（去重键）"""
        stmt = select(PolicyModel).where(PolicyModel.source_url == source_url)
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def save(self, policy: Policy) -> None:
        """按 source_url upsert：存在则更新业务字段，否则新建"""
        stmt = select(PolicyModel).where(PolicyModel.source_url == policy.source_url)
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        if not record:
            self.db_session.add(PolicyModel.from_domain(policy))
            return
        record.update_from_domain(policy)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        region: str = "",
        issuer: str = "",
        keyword: str = "",
    ) -> Tuple[List[Policy], int]:
        """分页+可选筛选返回(当前页列表, 总数)，按发文日期倒序(空日期殿后)"""
        conditions = []
        if region:
            conditions.append(PolicyModel.region.ilike(f"%{region}%"))
        if issuer:
            conditions.append(PolicyModel.issuer.ilike(f"%{issuer}%"))
        if keyword:
            conditions.append(PolicyModel.title.ilike(f"%{keyword}%"))

        count_stmt = select(func.count()).select_from(PolicyModel)
        list_stmt = select(PolicyModel)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            list_stmt = list_stmt.where(cond)

        total = (await self.db_session.execute(count_stmt)).scalar_one()
        list_stmt = (
            list_stmt.order_by(PolicyModel.publish_date.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = (await self.db_session.execute(list_stmt)).scalars().all()
        return [r.to_domain() for r in records], total
