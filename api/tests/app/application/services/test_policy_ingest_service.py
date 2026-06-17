"""PolicyIngestService 离线单测：按来源(source)选择爬虫入库（通用多区域框架）。

用内存级 UoW + 假 Embedding + 假爬虫，不依赖真实门户/DB/向量服务。
"""

import asyncio
import json
from datetime import date
from typing import List

import pytest

from app.application.errors.exceptions import BadRequestError
from app.application.services.policy_ingest_service import PolicyIngestService
from app.domain.models.policy import Policy

from ._fakes import FakeEmbedding, make_uow_factory


class FakeCrawler:
    """假爬虫：crawl 返回预置政策，记录被调用的页数。"""

    def __init__(self, policies: List[Policy]) -> None:
        self._policies = policies
        self.crawled_pages: int | None = None

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        self.crawled_pages = max_pages
        return self._policies


class FakeLLM:
    """假 LLM：对每次抽取返回预置 JSON content。"""

    def __init__(self, content: str) -> None:
        self._content = content

    async def invoke(self, messages, tools=None, response_format=None, tool_choice=None):
        return {"content": self._content}


def _policy(url: str, title: str, region: str) -> Policy:
    return Policy(source_url=url, title=title, body_text=f"{title} 正文", region=region,
                  publish_date=date(2026, 6, 1))


def _service(crawlers, llm=None, uow_factory=None):
    return PolicyIngestService(
        uow_factory=uow_factory or make_uow_factory(),
        crawlers=crawlers,
        embedding=FakeEmbedding(),
        llm=llm,
    )


def test_ingest_uses_selected_source() -> None:
    cq = FakeCrawler([_policy("cq-1", "重庆高企政策", "重庆市")])
    wnd = FakeCrawler([_policy("wnd-1", "新吴区政策", "江苏省无锡市新吴区")])
    service = _service({"wnd": wnd, "cq": cq})

    summary = asyncio.run(service.ingest("cq", max_pages=2))

    # 只跑了被选中的来源
    assert cq.crawled_pages == 2
    assert wnd.crawled_pages is None
    assert summary["source"] == "cq"
    assert summary["crawled"] == 1
    assert summary["upserted"] == 1


def test_ingest_unknown_source_raises() -> None:
    service = _service({"wnd": FakeCrawler([])})

    with pytest.raises(BadRequestError):
        asyncio.run(service.ingest("nope", max_pages=1))


def test_ingest_without_llm_leaves_deadline_unknown() -> None:
    store: dict = {}
    wnd = FakeCrawler([_policy("wnd-1", "新吴区政策", "江苏省无锡市新吴区")])
    service = _service({"wnd": wnd}, llm=None, uow_factory=make_uow_factory(policies=store))

    asyncio.run(service.ingest("wnd", max_pages=1))

    saved = store["wnd-1"]
    assert saved.deadline_status == "unknown"
    assert saved.apply_deadline is None


def test_ingest_with_llm_writes_extracted_deadline() -> None:
    store: dict = {}
    wnd = FakeCrawler([_policy("wnd-1", "高企申报", "江苏省无锡市新吴区")])
    llm = FakeLLM(json.dumps(
        {"found": True, "deadline": "2026-07-31", "rolling": False, "window": "7月底前"}
    ))
    service = _service({"wnd": wnd}, llm=llm, uow_factory=make_uow_factory(policies=store))

    asyncio.run(service.ingest("wnd", max_pages=1))

    saved = store["wnd-1"]
    assert saved.deadline_status == "extracted"
    assert saved.apply_deadline == date(2026, 7, 31)
    assert saved.apply_window_text == "7月底前"


def test_ingest_with_failing_llm_does_not_block_ingest() -> None:
    class _BoomLLM:
        async def invoke(self, *a, **k):
            raise RuntimeError("boom")

    store: dict = {}
    wnd = FakeCrawler([_policy("wnd-1", "政策", "江苏省无锡市新吴区")])
    service = _service({"wnd": wnd}, llm=_BoomLLM(), uow_factory=make_uow_factory(policies=store))

    summary = asyncio.run(service.ingest("wnd", max_pages=1))

    # LLM 抽取失败被吞，入库照常完成、截止字段安全回退 unknown
    assert summary["upserted"] == 1
    assert store["wnd-1"].deadline_status == "unknown"


def test_registry_lists_sources_and_builds_crawlers() -> None:
    from app.infrastructure.external.crawler.registry import build_crawlers, list_sources

    sources = list_sources()
    keys = {s.key for s in sources}
    assert "wnd" in keys  # 无锡新吴区为首版来源
    for s in sources:
        assert s.key and s.name and s.region

    crawlers = build_crawlers()
    assert set(crawlers.keys()) == keys
    # 每个来源都构造出一个可调用 crawl 的爬虫
    for crawler in crawlers.values():
        assert hasattr(crawler, "crawl")
