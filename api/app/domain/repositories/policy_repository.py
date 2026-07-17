from datetime import datetime
from typing import Dict, List, Optional, Protocol, Tuple

from app.domain.models.policy import Policy


class PolicyRepository(Protocol):
    """公开政策仓库协议定义（全局共享，非租户隔离）"""

    async def list_contests(
        self, page: int, page_size: int, origin: str = "", region: str = "",
        source: str = "", keyword: str = "", active_only: bool = False, tenant_id: str = "",
    ) -> Tuple[List[Policy], int]:
        ...

    async def get_by_id(self, policy_id: str) -> Optional[Policy]:
        """按政策id查询"""
        ...

    async def get_by_source_url(self, source_url: str) -> Optional[Policy]:
        """按详情页URL查询（去重键）"""
        ...

    async def list_by_source_urls(self, source_urls: List[str]) -> List[Policy]:
        """按一组 source_url 批量查询（③语义召回聚合后批量回查，避免 N+1）"""
        ...

    async def list_by_sources(self, sources: List[str], limit: int = 200) -> List[Policy]:
        """按来源批量查询，按发布日期/创建时间倒序返回，用于赛事摘要等批量只读场景"""
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

    async def stats_by_source(self) -> Dict[str, Tuple[int, Optional[datetime]]]:
        """按来源聚合统计：{source: (收录条数, 最近抓取时间)}，单条 GROUP BY，供「数据来源」页"""
        ...

    async def record_crawl(
        self, source: str, ran_at: datetime, new_count: int, crawled_count: int,
    ) -> None:
        """记录一次抓取运行(按 source upsert 最近运行时刻+结果计数)，供 0 条也刷新"最近更新" """
        ...

    async def crawl_run_times(self) -> Dict[str, datetime]:
        """{source: 最近一次抓取运行时刻}——与是否入库无关，供「数据来源」页优先展示"""
        ...

    async def distinct_contest_regions(self, sources: List[str]) -> List[str]:
        """给定赛事来源集合，返回其已入库政策的去重地区(供前端参赛地区选项数据驱动)，按地区名排序"""
        ...
