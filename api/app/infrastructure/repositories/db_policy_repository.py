from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.policy import Policy
from app.domain.repositories.policy_repository import PolicyRepository
from app.infrastructure.models import PolicyModel, SourceCrawlStateModel


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

    async def list_by_source_urls(self, source_urls: List[str]) -> List[Policy]:
        """按一组 source_url 批量查询（一次 IN 查询，避免逐条 N+1）"""
        if not source_urls:
            return []
        stmt = select(PolicyModel).where(PolicyModel.source_url.in_(source_urls))
        records = (await self.db_session.execute(stmt)).scalars().all()
        return [r.to_domain() for r in records]

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

    async def list_candidates(self, limit: int) -> List[Policy]:
        """取最近 limit 篇政策(含正文)作为③匹配的结构化候选集，按发文日期倒序(空日期殿后)"""
        stmt = (
            select(PolicyModel)
            .order_by(PolicyModel.publish_date.desc().nullslast())
            .limit(limit)
        )
        records = (await self.db_session.execute(stmt)).scalars().all()
        return [r.to_domain() for r in records]

    async def stats_by_source(self) -> Dict[str, Tuple[int, Optional[datetime]]]:
        """按来源聚合：{source: (条数, 最近抓取时间)}，单条 GROUP BY 查询(无 N+1)"""
        stmt = select(
            PolicyModel.source,
            func.count().label("cnt"),
            func.max(PolicyModel.crawled_at).label("last_crawled_at"),
        ).group_by(PolicyModel.source)
        rows = (await self.db_session.execute(stmt)).all()
        return {row.source: (row.cnt, row.last_crawled_at) for row in rows}

    async def record_crawl(
        self, source: str, ran_at: datetime, new_count: int, crawled_count: int,
    ) -> None:
        """按 source upsert 最近一次抓取运行状态(抓到 0 条也更新时刻)。"""
        record = await self.db_session.get(SourceCrawlStateModel, source)
        if record is None:
            record = SourceCrawlStateModel(source=source)
            self.db_session.add(record)
        record.last_crawled_at = ran_at
        record.last_new_count = new_count
        record.last_crawled_count = crawled_count

    async def crawl_run_times(self) -> Dict[str, datetime]:
        """{source: 最近一次抓取运行时刻}"""
        rows = (await self.db_session.execute(
            select(SourceCrawlStateModel.source, SourceCrawlStateModel.last_crawled_at)
        )).all()
        return {row.source: row.last_crawled_at for row in rows}

    async def distinct_contest_regions(self, sources: List[str]) -> List[str]:
        """赛事来源已入库政策的去重地区(供前端参赛地区选项数据驱动)，按地区名排序"""
        if not sources:
            return []
        stmt = (
            select(PolicyModel.region)
            .where(PolicyModel.source.in_(sources), PolicyModel.region != "")
            .distinct()
            .order_by(PolicyModel.region)
        )
        rows = (await self.db_session.execute(stmt)).scalars().all()
        return [r for r in rows if r]
