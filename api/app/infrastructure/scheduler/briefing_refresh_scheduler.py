"""主动情报简报定时重算调度器（主动情报 Agent）。

"主动"的临门一脚：Agent 在企业用户离线时，按 cron 自主为所有已建档租户重新生成
"带理由的优先级机会简报"，让用户回来即看到"我帮你盯着、本期有这些机会"。

挂在 api 进程的 asyncio 事件循环上(AsyncIOScheduler)，复用进程内连接（与公开政策重爬
调度器同构）。best-effort：单次/单租户失败只记 warning，不影响应用；单实例假设。
"""

import logging
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class BriefingRefreshScheduler:
    """按 cron 周期为所有已建档租户重算情报简报的应用内调度器。"""

    def __init__(
        self,
        hour: int,
        minute: int,
        regenerate_all: Callable[[], Awaitable[int]],
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self._hour = hour
        self._minute = minute
        self._regenerate_all = regenerate_all
        self._timezone = timezone
        self._scheduler: AsyncIOScheduler | None = None

    def start(self) -> None:
        """登记 cron 任务并启动调度器。"""
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._run,
            trigger=CronTrigger(hour=self._hour, minute=self._minute, timezone=self._timezone),
            id="briefing_refresh",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )
        self._scheduler.start()
        logger.info(
            "主动情报简报调度器已启动：每天 %02d:%02d(%s) 为已建档租户重算简报",
            self._hour, self._minute, self._timezone,
        )

    async def _run(self) -> None:
        """触发批量重算；整体异常 best-effort 吞掉，不冒泡。"""
        try:
            count = await self._regenerate_all()
            logger.info("主动情报简报定时重算完成：%d 个租户", count)
        except Exception as e:  # noqa: BLE001 — 定时任务 best-effort
            logger.warning("主动情报简报定时重算失败: %s: %s", type(e).__name__, e)

    def shutdown(self) -> None:
        """停止调度器（应用关闭时调用）。"""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("主动情报简报调度器已停止")
