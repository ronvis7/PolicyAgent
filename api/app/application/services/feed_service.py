"""工作台 Feed 服务（主线④）。

在 ③ 即时匹配之上做**物化**：把候选政策落 `policy_matches` 表，形成持久化信息流，
据此判「新增」(未读红点)、免每次重算。重算语义是关键：
- 新出现的候选 → 插入 unread(即"新增")；
- 已存在的 → 只更新计算快照，**保留 status 与 created_at**(不冲掉用户已申报/已忽略)；
- 跌出候选的旧条目 → 保留不删(可能已申报/想留存)。

触发由端点侧接线：(a)抓取政策入库后、(b)企业档案保存后，重算**当前租户**；
(c)Feed 页「重新匹配」手动重算(兜住跨租户：别人抓的新政策本租户点一下即可拉到)。
"""

import logging
from datetime import datetime
from typing import Callable, List, Optional, Protocol, Tuple

from app.application.errors.exceptions import NotFoundError
from app.domain.models.feed_item import FeedItem, FeedStatus
from app.domain.models.policy_match import PolicyMatch
from app.domain.models.qualification import QualificationMatch
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)

# 每次重算纳入 Feed 的候选上限(与③默认 top_k 对齐，足够覆盖一个区的可申报政策)
DEFAULT_FEED_TOP_K = 20


class MatchService(Protocol):
    """重算所需的政策匹配能力(由 PolicyMatchService 实现)，按协议解耦便于测试。"""

    async def match_for_tenant(self, tenant_id: str, top_k: int = ...) -> List[PolicyMatch]:
        ...


class QualificationMatchService(Protocol):
    """重算所需的资质匹配能力(由 QualificationService 实现，⑥机会第二类)。"""

    async def match_for_tenant(self, tenant_id: str, top_k: int = ...) -> List[QualificationMatch]:
        ...


class FeedService:
    """工作台 Feed 服务：物化③政策匹配 + ⑥资质匹配结果 + 状态机管理。"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        match_service: MatchService,
        qualification_service: Optional[QualificationMatchService] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._match_service = match_service
        self._qualification_service = qualification_service

    async def recompute_for_tenant(
        self, tenant_id: str, top_k: int = DEFAULT_FEED_TOP_K,
    ) -> dict:
        """重算当前租户 Feed：政策+资质两类机会一并物化(新增 unread / 更新快照保留用户状态)。

        返回 {new, updated}。资质源缺省(qualification_service=None)时只跑政策，保持向后兼容。
        """
        fresh_items = await self._collect_fresh_items(tenant_id, top_k)

        new_count = 0
        updated_count = 0
        async with self._uow_factory() as uow:
            for fresh in fresh_items:
                existing = await uow.feed.get_by_tenant_and_policy(
                    tenant_id, fresh.policy_id,
                )
                if existing is None:
                    await uow.feed.save(fresh)  # 新增 → unread → 驱动红点
                    new_count += 1
                else:
                    # 只更新计算快照，保留 id/status/created_at
                    await uow.feed.save(existing.with_snapshot_from(fresh))
                    updated_count += 1

        logger.info(
            "Feed 重算完成 tenant=%s new=%d updated=%d", tenant_id, new_count, updated_count,
        )
        return {"new": new_count, "updated": updated_count}

    async def _collect_fresh_items(self, tenant_id: str, top_k: int) -> List[FeedItem]:
        """汇集政策与资质两类机会，统一转为待 upsert 的 FeedItem 列表。"""
        matches = await self._match_service.match_for_tenant(tenant_id, top_k=top_k)
        items = [FeedItem.from_policy_match(tenant_id, m) for m in matches]

        if self._qualification_service is not None:
            qual_matches = await self._qualification_service.match_for_tenant(tenant_id)
            items.extend(FeedItem.from_qualification_match(tenant_id, qm) for qm in qual_matches)

        return items

    async def list_feed(
        self,
        tenant_id: str,
        status: Optional[FeedStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[FeedItem], int]:
        """分页返回当前租户 Feed(可按状态过滤)，按创建时间倒序。"""
        async with self._uow_factory() as uow:
            return await uow.feed.list_paginated(tenant_id, status, page, page_size)

    async def unread_count(self, tenant_id: str) -> int:
        """当前租户未读条数(左栏红点)。"""
        async with self._uow_factory() as uow:
            return await uow.feed.count_by_status(tenant_id, FeedStatus.UNREAD)

    async def set_status(
        self, tenant_id: str, item_id: str, status: FeedStatus,
    ) -> FeedItem:
        """更新某条 Feed 状态(read/applied/ignored)，校验归属当前租户。"""
        async with self._uow_factory() as uow:
            item = await uow.feed.get_by_id(tenant_id, item_id)
            if item is None:
                raise NotFoundError(msg="Feed 条目不存在或无权访问")
            updated = item.model_copy(update={"status": status, "updated_at": datetime.now()})
            await uow.feed.save(updated)
            return updated

    async def mark_all_read(self, tenant_id: str) -> int:
        """打开工作台时把当前租户全部未读置为已读，返回受影响条数。"""
        async with self._uow_factory() as uow:
            return await uow.feed.mark_all_read(tenant_id)
