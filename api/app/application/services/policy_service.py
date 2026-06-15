"""公开政策库读服务：分页浏览 + 详情。

公开政策库为全局共享层(非租户隔离)，所有登录用户均可浏览。本服务只读，
入库/爬取由 PolicyIngestService 负责。
"""

import logging
from typing import Callable, List, Tuple

from app.application.errors.exceptions import NotFoundError
from app.domain.models.policy import Policy
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)

# 分页边界，防止非法/超大 page_size 拖垮查询
_MIN_PAGE = 1
_MIN_PAGE_SIZE = 1
_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 20


class PolicyService:
    """公开政策库读服务(全局共享，分页浏览 + 详情)"""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def list_policies(
        self,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        region: str = "",
        issuer: str = "",
        keyword: str = "",
    ) -> Tuple[List[Policy], int]:
        """分页+可选筛选浏览政策，返回(当前页列表, 总数)。规整分页参数到合法区间。"""
        page = max(_MIN_PAGE, page)
        page_size = max(_MIN_PAGE_SIZE, min(_MAX_PAGE_SIZE, page_size))
        async with self._uow_factory() as uow:
            return await uow.policy.list_paginated(
                page=page,
                page_size=page_size,
                region=region.strip(),
                issuer=issuer.strip(),
                keyword=keyword.strip(),
            )

    async def get_policy(self, policy_id: str) -> Policy:
        """获取政策详情，不存在则抛 NotFound"""
        async with self._uow_factory() as uow:
            policy = await uow.policy.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"政策[{policy_id}]不存在")
        return policy
