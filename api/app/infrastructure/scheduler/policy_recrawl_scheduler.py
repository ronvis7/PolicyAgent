"""公开政策定时重爬调度器（主线⑤：保鲜申报通知的申报截止日期）。

申报通知的申报窗口可能只有 1-2 周，需周期性重爬才能让临期提醒"活"起来。本调度器挂在
api 进程的 asyncio 事件循环上(AsyncIOScheduler)，按 cron 触发 PolicyIngestService.ingest，
复用进程内 DB/Embedding/LLM 连接——这是当前(stack 跑在开发机、连共享远程库)架构下唯一自洽的
做法：云端定时到不了本地栈，远程库服务器无应用代码。

best-effort：单次抓取失败只记 warning，不影响应用运行；幂等(按 source_url upsert + 切片替换)，
重复跑安全。单实例假设(当前单 api 容器)；多副本需引入分布式锁避免并发重复抓取。
"""

import logging
from typing import Awaitable, Callable, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class PolicyRecrawlScheduler:
    """按 cron 周期触发公开政策重爬的应用内调度器。"""

    def __init__(
        self,
        sources: List[str],
        hour: int,
        minute: int,
        max_pages: int,
        ingest: Callable[[str, int], Awaitable[dict]],
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self._sources = sources
        self._hour = hour
        self._minute = minute
        self._max_pages = max_pages
        self._ingest = ingest
        self._timezone = timezone
        self._scheduler: AsyncIOScheduler | None = None

    def start(self) -> None:
        """登记 cron 任务并启动调度器(无来源则不启动)。"""
        if not self._sources:
            logger.info("公开政策重爬：未配置来源，调度器不启动")
            return
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._run,
            trigger=CronTrigger(hour=self._hour, minute=self._minute, timezone=self._timezone),
            id="policy_recrawl",
            replace_existing=True,
            misfire_grace_time=3600,  # 进程晚启动/卡顿时仍允许 1h 内补跑
            coalesce=True,            # 多次错过只合并跑一次
        )
        self._scheduler.start()
        logger.info(
            "公开政策重爬调度器已启动：每天 %02d:%02d(%s) 重爬 %s(max_pages=%d)",
            self._hour, self._minute, self._timezone, self._sources, self._max_pages,
        )

    async def _run(self) -> None:
        """逐来源 best-effort 重爬；单源失败不影响其他源。"""
        for source in self._sources:
            try:
                summary = await self._ingest(source, self._max_pages)
                logger.info("公开政策定时重爬完成 source=%s summary=%s", source, summary)
            except Exception as e:  # noqa: BLE001 — 定时任务 best-effort，不冒泡
                logger.warning(
                    "公开政策定时重爬失败 source=%s: %s: %s", source, type(e).__name__, e,
                )

    def shutdown(self) -> None:
        """停止调度器(应用关闭时调用)；不等待在跑任务，避免阻塞关闭。"""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("公开政策重爬调度器已停止")
