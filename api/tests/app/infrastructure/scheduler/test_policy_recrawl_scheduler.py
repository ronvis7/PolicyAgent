"""PolicyRecrawlScheduler 离线单测：best-effort 重爬语义与启停守卫，不真正起 cron。"""

import asyncio

from app.infrastructure.scheduler.policy_recrawl_scheduler import PolicyRecrawlScheduler


def _scheduler(sources, ingest):
    return PolicyRecrawlScheduler(
        sources=sources, hour=4, minute=0, max_pages=3, ingest=ingest,
    )


def test_run_invokes_ingest_for_each_source() -> None:
    calls = []

    async def fake_ingest(source, max_pages):
        calls.append((source, max_pages))
        return {"source": source, "indexed": 1}

    sched = _scheduler(["wnd-apply", "wnd"], fake_ingest)
    asyncio.run(sched._run())

    assert calls == [("wnd-apply", 3), ("wnd", 3)]


def test_run_is_best_effort_one_source_failure_does_not_block_others() -> None:
    calls = []

    async def flaky_ingest(source, max_pages):
        calls.append(source)
        if source == "wnd-apply":
            raise RuntimeError("crawl boom")
        return {"source": source}

    sched = _scheduler(["wnd-apply", "wnd"], flaky_ingest)
    # 第一源抛错被吞，第二源仍执行
    asyncio.run(sched._run())

    assert calls == ["wnd-apply", "wnd"]


def test_start_with_no_sources_does_not_start_scheduler() -> None:
    sched = _scheduler([], lambda s, m: None)
    sched.start()
    assert sched._scheduler is None


def test_start_then_shutdown_lifecycle() -> None:
    # 起一个真实 AsyncIOScheduler 需要事件循环；在协程内启动后立即关闭
    async def main():
        async def noop(source, max_pages):
            return {}
        sched = _scheduler(["wnd-apply"], noop)
        sched.start()
        assert sched._scheduler is not None
        sched.shutdown()
        assert sched._scheduler is None

    asyncio.run(main())
