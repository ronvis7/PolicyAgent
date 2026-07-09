"""真仓储来源统计回归(连真库)：验证 stats_by_source 的 GROUP BY 聚合正确。

政策库为全局共享(无 tenant)，与其他行共存。为不受存量数据干扰，用随机 source key
种入若干政策，仅断言该 source 的聚合结果(条数 + 最近抓取时间取 max)。
"""

import asyncio
import uuid
from datetime import datetime

from app.domain.models.policy import Policy


def test_stats_by_source_counts_and_latest_crawl(uow_factory):
    async def body():
        src = f"itest-src-{uuid.uuid4().hex[:8]}"
        latest = datetime(2026, 6, 18, 9, 0)
        async with uow_factory() as uow:
            await uow.policy.save(Policy(
                source=src, source_url=f"https://x/{uuid.uuid4()}", title="政1",
                crawled_at=datetime(2026, 6, 10, 9, 0),
            ))
            await uow.policy.save(Policy(
                source=src, source_url=f"https://x/{uuid.uuid4()}", title="政2",
                crawled_at=latest,
            ))

        async with uow_factory() as uow:
            stats = await uow.policy.stats_by_source()

        assert src in stats
        count, last_crawled_at = stats[src]
        assert count == 2
        # 取该来源最近一次抓取时间(忽略可能的时区/微秒差异，比到分钟)
        assert last_crawled_at is not None
        assert last_crawled_at.replace(microsecond=0, tzinfo=None) == latest

    asyncio.run(body())


def test_record_crawl_upserts_and_run_times_reflect_zero_result(uow_factory):
    """抓取运行记录：按 source upsert，crawl_run_times 反映最近运行时刻(0 条也记录)。"""
    async def body():
        src = f"itest-run-{uuid.uuid4().hex[:8]}"
        async with uow_factory() as uow:
            await uow.policy.record_crawl(src, datetime(2026, 7, 1, 3, 0), 5, 12)
        async with uow_factory() as uow:
            await uow.policy.record_crawl(src, datetime(2026, 7, 9, 3, 0), 0, 0)  # 0 条也更新

        async with uow_factory() as uow:
            times = await uow.policy.crawl_run_times()

        assert src in times
        assert times[src].replace(microsecond=0, tzinfo=None) == datetime(2026, 7, 9, 3, 0)

    asyncio.run(body())
