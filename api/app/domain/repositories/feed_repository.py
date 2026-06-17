from datetime import date
from typing import List, Optional, Protocol, Tuple

from app.domain.models.feed_item import FeedItem, FeedStatus


class FeedRepository(Protocol):
    """工作台 Feed 条目仓库协议(④：物化的政策/机会信息流，按租户隔离)"""

    async def get_by_tenant_and_policy(
        self, tenant_id: str, policy_id: str,
    ) -> Optional[FeedItem]:
        """按 (租户, 机会源id) 自然键查询(重算判定新增/更新用)"""
        ...

    async def get_by_id(self, tenant_id: str, item_id: str) -> Optional[FeedItem]:
        """按 id 查询并校验归属当前租户(跨租户访问返回 None)"""
        ...

    async def save(self, item: FeedItem) -> None:
        """按 (租户, 机会源id) upsert：存在则整体更新，否则新建"""
        ...

    async def list_paginated(
        self,
        tenant_id: str,
        status: Optional[FeedStatus],
        page: int,
        page_size: int,
    ) -> Tuple[List[FeedItem], int]:
        """分页返回当前租户 Feed(status=None 不过滤)，按创建时间倒序，返回(当前页, 总数)"""
        ...

    async def count_by_status(self, tenant_id: str, status: FeedStatus) -> int:
        """统计当前租户某状态条目数(未读红点用)"""
        ...

    async def list_expiring(
        self, tenant_id: str, today: date, until: date,
    ) -> List[FeedItem]:
        """返回当前租户申报截止落在 [today, until] 内且未忽略的条目，按截止日期升序(最紧的在前)。

        主线⑤ 临期提醒：只取 deadline_status=extracted(有明确日期)且未 ignored 的机会。
        """
        ...

    async def mark_all_read(self, tenant_id: str) -> int:
        """把当前租户所有 unread 批量置为 read，返回受影响条数"""
        ...
