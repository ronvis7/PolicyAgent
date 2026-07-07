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


def _service(crawlers, llm=None, uow_factory=None, on_new_policies=None,
             skip_expired_sources=None):
    return PolicyIngestService(
        uow_factory=uow_factory or make_uow_factory(),
        crawlers=crawlers,
        embedding=FakeEmbedding(),
        llm=llm,
        on_new_policies=on_new_policies,
        skip_expired_sources=skip_expired_sources,
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


def test_ingest_summary_distinguishes_new_from_updated() -> None:
    """summary 报告本次新增条数(new)：区分首次入库与既有政策的 upsert 更新。"""
    store: dict = {}
    uow_factory = make_uow_factory(policies=store)
    wnd = FakeCrawler([_policy("wnd-1", "政策一", "江苏省无锡市新吴区")])
    service = _service({"wnd": wnd}, uow_factory=uow_factory)

    first = asyncio.run(service.ingest("wnd", max_pages=1))
    assert first["new"] == 1

    # 同一批再入库：全部是更新，无新增
    second = asyncio.run(service.ingest("wnd", max_pages=1))
    assert second["new"] == 0
    assert second["upserted"] == 1


def test_ingest_calls_on_new_policies_hook_with_only_new_items() -> None:
    """钩子只收到本次真正新增的政策(新赛事即推的依据)，已存在的不重复推。"""
    store: dict = {}
    uow_factory = make_uow_factory(policies=store)
    received: list = []

    async def hook(source: str, policies: List[Policy]) -> None:
        received.append((source, [p.source_url for p in policies]))

    old = _policy("wnd-old", "既有政策", "江苏省无锡市新吴区")
    crawler = FakeCrawler([old, _policy("wnd-new", "新大赛通知", "江苏省无锡市新吴区")])
    service = _service({"wnd": crawler}, uow_factory=uow_factory, on_new_policies=hook)

    # 预置既有政策
    asyncio.run(_service({"pre": FakeCrawler([old])}, uow_factory=uow_factory).ingest("pre"))

    asyncio.run(service.ingest("wnd", max_pages=1))

    assert received[-1] == ("wnd", ["wnd-new"])


def test_ingest_does_not_call_hook_when_nothing_new() -> None:
    store: dict = {}
    uow_factory = make_uow_factory(policies=store)
    calls: list = []

    async def hook(source: str, policies: List[Policy]) -> None:
        calls.append(source)

    wnd = FakeCrawler([_policy("wnd-1", "政策一", "江苏省无锡市新吴区")])
    service = _service({"wnd": wnd}, uow_factory=uow_factory, on_new_policies=hook)

    asyncio.run(service.ingest("wnd"))
    asyncio.run(service.ingest("wnd"))  # 第二次无新增

    assert calls == ["wnd"]


def test_ingest_dedupes_new_policies_by_source_url() -> None:
    """同批爬取的跨页重复条目(如 gxt dataproxy 重叠)只算一次新增、只推一次。

    upsert/索引也必须按去重后的批次执行：真库 save 是"查存量、无则 INSERT"，
    同事务内第二条重复 url 看不到未提交的第一条，双双 INSERT 会撞
    uq_policies_source_url 唯一约束导致整批回滚(gxt-contest 真机曾复现)。
    """
    store: dict = {}
    uow_factory = make_uow_factory(policies=store)
    received: list = []

    async def hook(source: str, policies: List[Policy]) -> None:
        received.append([p.source_url for p in policies])

    dup_a = _policy("wnd-1", "大赛通知", "江苏省无锡市新吴区")
    dup_b = _policy("wnd-1", "大赛通知", "江苏省无锡市新吴区")
    service = _service({"wnd": FakeCrawler([dup_a, dup_b])},
                       uow_factory=uow_factory, on_new_policies=hook)

    summary = asyncio.run(service.ingest("wnd"))

    assert summary["crawled"] == 1
    assert summary["upserted"] == 1
    assert summary["new"] == 1
    assert received == [["wnd-1"]]


def test_ingest_hook_failure_does_not_block_ingest() -> None:
    """推送钩子 best-effort：钩子抛错不影响入库结果。"""
    store: dict = {}

    async def boom(source: str, policies: List[Policy]) -> None:
        raise RuntimeError("webhook down")

    wnd = FakeCrawler([_policy("wnd-1", "政策一", "江苏省无锡市新吴区")])
    service = _service({"wnd": wnd},
                       uow_factory=make_uow_factory(policies=store), on_new_policies=boom)

    summary = asyncio.run(service.ingest("wnd"))

    assert summary["upserted"] == 1
    assert summary["new"] == 1
    assert "wnd-1" in store


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


def _expired_deadline_llm() -> FakeLLM:
    return FakeLLM(json.dumps(
        {"found": True, "deadline": "2020-01-01", "rolling": False, "window": "已截止"}
    ))


def test_ingest_skips_expired_contest_for_competition_sources() -> None:
    """赛事来源抽出申报截止且已过期：不入库、不向量化、不推送(比赛过期即失效)。"""
    store: dict = {}
    received: list = []

    async def hook(source, policies):
        received.append([p.source_url for p in policies])

    crawler = FakeCrawler([_policy("c-1", "关于举办大赛的通知", "江苏省")])
    service = _service({"gxt-contest": crawler}, llm=_expired_deadline_llm(),
                       uow_factory=make_uow_factory(policies=store),
                       on_new_policies=hook, skip_expired_sources={"gxt-contest"})

    summary = asyncio.run(service.ingest("gxt-contest"))

    assert summary["upserted"] == 0
    assert summary["new"] == 0
    assert summary["skipped_expired"] == 1
    assert store == {}
    assert received == []


def test_ingest_keeps_expired_deadline_for_policy_sources() -> None:
    """非赛事来源不受过期跳过影响：政策长期有效，历史截止仅供展示。"""
    store: dict = {}
    crawler = FakeCrawler([_policy("p-1", "申报通知", "江苏省")])
    service = _service({"wnd-apply": crawler}, llm=_expired_deadline_llm(),
                       uow_factory=make_uow_factory(policies=store),
                       skip_expired_sources={"gxt-contest", "wnd-contest"})

    summary = asyncio.run(service.ingest("wnd-apply"))

    assert summary["upserted"] == 1
    assert summary["skipped_expired"] == 0
    assert "p-1" in store


def test_ingest_keeps_contest_with_unknown_deadline() -> None:
    """赛事条目抽不出截止(unknown)时保留：不误杀，时效窗口在爬虫层兜底。"""
    store: dict = {}
    crawler = FakeCrawler([_policy("c-1", "关于举办大赛的通知", "江苏省")])
    service = _service({"wnd-contest": crawler}, llm=None,
                       uow_factory=make_uow_factory(policies=store),
                       skip_expired_sources={"wnd-contest"})

    summary = asyncio.run(service.ingest("wnd-contest"))

    assert summary["upserted"] == 1
    assert summary["skipped_expired"] == 0
    assert "c-1" in store
