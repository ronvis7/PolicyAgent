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

    async def list_by_source_urls(self, source_urls: List[str]) -> List[Policy]:
        """按一组 source_url 批量查询（③语义召回聚合后批量回查，避免 N+1）"""
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

    async def list_candidates(self, limit: int) -> List[Policy]:
        """取最近 limit 篇政策(含正文)作为③匹配的结构化候选集，按发文日期倒序"""
        ...
