from typing import List, Optional, Protocol, Tuple

from app.domain.models.policy import Policy


class PolicyRepository(Protocol):
    """公开政策仓库协议定义（全局共享，非租户隔离）"""

    async def get_by_id(self, policy_id: str) -> Optional[Policy]:
        """按政策id查询"""
        ...

    async def get_by_source_url(self, source_url: str) -> Optional[Policy]:
        """按详情页URL查询（去重键）"""
        ...

    async def save(self, policy: Policy) -> None:
        """按 source_url upsert：存在则更新业务字段，否则新建"""
        ...

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        region: str = "",
        issuer: str = "",
        keyword: str = "",
    ) -> Tuple[List[Policy], int]:
        """分页+可选筛选(地区/发文机构/标题关键词)返回(当前页列表, 总数)，按发文日期倒序"""
        ...
