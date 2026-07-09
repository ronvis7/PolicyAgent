"""公开政策库读服务：分页浏览 + 详情。

公开政策库为全局共享层(非租户隔离)，所有登录用户均可浏览。本服务只读，
入库/爬取由 PolicyIngestService 负责。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from app.application.errors.exceptions import NotFoundError
from app.domain.models.policy import Policy
from app.domain.repositories.uow import IUnitOfWork
from app.infrastructure.external.crawler.registry import competition_source_keys, list_sources

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceWithStats:
    """政策来源 + 收录统计(供「数据来源」透明页)"""
    key: str
    name: str
    region: str
    home_url: str
    policy_count: int
    last_crawled_at: Optional[datetime]
    item_type: str = "policy"  # 该来源产出的机会类型(policy/competition，前端据此生成参赛地区选项)

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

    async def list_sources_with_stats(self) -> List[SourceWithStats]:
        """列出已登记来源并附收录统计(条数/最近抓取时间)，供「数据来源」页溯源。

        来源元信息取自注册表，统计经单条 GROUP BY 聚合；某来源尚无政策则回落 0 / None。
        "最近更新"优先取抓取运行记录(抓到 0 条也刷新)，无记录时回落 MAX(policies.crawled_at)，
        使"跑过但 0 条"不再一直显示"尚未抓取"。
        """
        async with self._uow_factory() as uow:
            stats = await uow.policy.stats_by_source()
            crawl_run_times = await uow.policy.crawl_run_times()
        result: List[SourceWithStats] = []
        for s in list_sources():
            count, max_crawled_at = stats.get(s.key, (0, None))
            last_crawled_at = crawl_run_times.get(s.key) or max_crawled_at
            result.append(SourceWithStats(
                key=s.key, name=s.name, region=s.region, home_url=s.home_url,
                policy_count=count, last_crawled_at=last_crawled_at,
                item_type=s.item_type.value,
            ))
        return result

    async def list_contest_regions(self) -> List[str]:
        """列出实际有赛事入库的地区(去重、排序)，供前端「参赛关注地区」选项数据驱动。

        选项取自赛事来源(item_type=competition)已入库政策的 region，而非来源注册表的
        静态 region——因创客中国等来源"一源多地区"，且只展示真有数据的地区更贴合体验。
        """
        sources = list(competition_source_keys())
        if not sources:
            return []
        async with self._uow_factory() as uow:
            return await uow.policy.distinct_contest_regions(sources)

    async def get_policy(self, policy_id: str) -> Policy:
        """获取政策详情，不存在则抛 NotFound"""
        async with self._uow_factory() as uow:
            policy = await uow.policy.get_by_id(policy_id)
        if not policy:
            raise NotFoundError(f"政策[{policy_id}]不存在")
        return policy
