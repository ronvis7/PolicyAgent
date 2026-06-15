from typing import List, Optional, Tuple

from sqlalchemy import func, select, update

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.feed_item import FeedItem, FeedStatus
from app.domain.repositories.feed_repository import FeedRepository
from app.infrastructure.models import FeedItemModel


class DBFeedRepository(FeedRepository):
    """基于Postgres数据库的工作台 Feed 仓库（按租户隔离）"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_by_tenant_and_policy(
        self, tenant_id: str, policy_id: str,
    ) -> Optional[FeedItem]:
        """按 (租户, 机会源id) 自然键查询"""
        stmt = select(FeedItemModel).where(
            FeedItemModel.tenant_id == tenant_id,
            FeedItemModel.policy_id == policy_id,
        )
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def get_by_id(self, tenant_id: str, item_id: str) -> Optional[FeedItem]:
        """按 id 查询并校验归属当前租户(跨租户返回 None)"""
        stmt = select(FeedItemModel).where(
            FeedItemModel.id == item_id,
            FeedItemModel.tenant_id == tenant_id,
        )
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def save(self, item: FeedItem) -> None:
        """按 (租户, 机会源id) upsert：存在则整体更新，否则新建"""
        stmt = select(FeedItemModel).where(
            FeedItemModel.tenant_id == item.tenant_id,
            FeedItemModel.policy_id == item.policy_id,
        )
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        if not record:
            self.db_session.add(FeedItemModel.from_domain(item))
            return
        record.update_from_domain(item)

    async def list_paginated(
        self,
        tenant_id: str,
        status: Optional[FeedStatus],
        page: int,
        page_size: int,
    ) -> Tuple[List[FeedItem], int]:
        """分页返回当前租户 Feed(status=None 不过滤)，按创建时间倒序"""
        conditions = [FeedItemModel.tenant_id == tenant_id]
        if status is not None:
            conditions.append(FeedItemModel.status == status.value)

        count_stmt = select(func.count()).select_from(FeedItemModel)
        list_stmt = select(FeedItemModel)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            list_stmt = list_stmt.where(cond)

        total = (await self.db_session.execute(count_stmt)).scalar_one()
        list_stmt = (
            list_stmt.order_by(FeedItemModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = (await self.db_session.execute(list_stmt)).scalars().all()
        return [r.to_domain() for r in records], total

    async def count_by_status(self, tenant_id: str, status: FeedStatus) -> int:
        """统计当前租户某状态条目数"""
        stmt = (
            select(func.count())
            .select_from(FeedItemModel)
            .where(
                FeedItemModel.tenant_id == tenant_id,
                FeedItemModel.status == status.value,
            )
        )
        return (await self.db_session.execute(stmt)).scalar_one()

    async def mark_all_read(self, tenant_id: str) -> int:
        """把当前租户所有 unread 批量置为 read，返回受影响条数(单条 UPDATE，免逐条加载)"""
        stmt = (
            update(FeedItemModel)
            .where(
                FeedItemModel.tenant_id == tenant_id,
                FeedItemModel.status == FeedStatus.UNREAD.value,
            )
            .values(status=FeedStatus.READ.value)
        )
        result = await self.db_session.execute(stmt)
        return result.rowcount or 0
