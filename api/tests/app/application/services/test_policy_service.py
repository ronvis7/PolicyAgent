"""PolicyService + PolicyIngestService 离线单元测试。

异步方法用 asyncio.run 驱动(与本仓库其他测试一致)。
"""

import asyncio
from datetime import date, datetime
from typing import List

import pytest

from app.application.errors.exceptions import NotFoundError
from app.application.services.policy_ingest_service import (
    PUBLIC_KB_ID,
    PUBLIC_TENANT_ID,
    PolicyIngestService,
)
from app.application.services.policy_service import PolicyService
from app.domain.models.policy import Policy

from ._fakes import FakeEmbedding, make_uow_factory


def _policy(url: str, title: str, region: str = "江苏省无锡市新吴区", issuer: str = "",
            d: date = date(2026, 6, 1), body: str = "") -> Policy:
    return Policy(source="wnd", source_url=url, title=title, region=region,
                  issuer=issuer, publish_date=d, body_text=body)


# ---------- PolicyService 读 ----------

def test_list_paginated_returns_page_and_total() -> None:
    store = {}
    factory = make_uow_factory(policies=store)
    # 直接灌入 3 条
    for i in range(3):
        store[f"u{i}"] = _policy(f"u{i}", f"政策{i}", d=date(2026, 6, i + 1))
    service = PolicyService(uow_factory=factory)

    items, total = asyncio.run(service.list_policies(page=1, page_size=2))

    assert total == 3
    assert len(items) == 2
    assert items[0].title == "政策2"  # 按发文日期倒序


def test_list_filters_by_keyword_and_issuer() -> None:
    store = {
        "a": _policy("a", "高新技术企业认定奖励", issuer="科技局"),
        "b": _policy("b", "促消费措施", issuer="商务局"),
    }
    service = PolicyService(uow_factory=make_uow_factory(policies=store))

    items, total = asyncio.run(service.list_policies(keyword="高新"))
    assert total == 1 and items[0].source_url == "a"

    items2, total2 = asyncio.run(service.list_policies(issuer="商务"))
    assert total2 == 1 and items2[0].source_url == "b"


def test_list_clamps_page_size() -> None:
    service = PolicyService(uow_factory=make_uow_factory(policies={}))
    # page_size 超界不报错，规整到合法区间(返回空但不抛)
    items, total = asyncio.run(service.list_policies(page=0, page_size=9999))
    assert items == [] and total == 0


def test_get_policy_found_and_not_found() -> None:
    p = _policy("u1", "某政策")
    service = PolicyService(uow_factory=make_uow_factory(policies={"u1": p}))

    got = asyncio.run(service.get_policy(p.id))
    assert got.title == "某政策"

    with pytest.raises(NotFoundError):
        asyncio.run(service.get_policy("missing-id"))


# ---------- PolicyService 来源 + 统计 ----------

def test_list_sources_with_stats_merges_registry_and_counts() -> None:
    """已登记来源全部返回；有政策的源带条数，无政策的源回落 0/None。"""
    store = {
        "w1": Policy(source="wnd", source_url="w1", title="无锡政策1",
                     crawled_at=datetime(2026, 6, 10, 8, 0)),
        "w2": Policy(source="wnd", source_url="w2", title="无锡政策2",
                     crawled_at=datetime(2026, 6, 18, 8, 0)),
        "s1": Policy(source="shyp", source_url="s1", title="杨浦政策1",
                     crawled_at=datetime(2026, 6, 15, 8, 0)),
    }
    service = PolicyService(uow_factory=make_uow_factory(policies=store))

    sources = asyncio.run(service.list_sources_with_stats())
    by_key = {s.key: s for s in sources}

    # 注册表三条来源全部返回(wnd / wnd-apply / shyp)
    assert {"wnd", "wnd-apply", "shyp"} <= set(by_key)
    # 有政策的源：条数 + 最近抓取时间(取 max)
    assert by_key["wnd"].policy_count == 2
    assert by_key["wnd"].last_crawled_at == datetime(2026, 6, 18, 8, 0)
    assert by_key["shyp"].policy_count == 1
    # 无政策的源回落 0 / None，但元信息(官网链接)仍在
    assert by_key["wnd-apply"].policy_count == 0
    assert by_key["wnd-apply"].last_crawled_at is None
    assert by_key["wnd"].home_url.startswith("http")
    # 机会类型透出：赛事子源=competition、政策来源=policy(前端据此生成参赛地区选项)
    assert by_key["wnd-contest"].item_type == "competition"
    assert by_key["wnd"].item_type == "policy"


def test_list_contest_regions_dedupes_from_competition_sources_only() -> None:
    """参赛地区选项：数据驱动(赛事来源去重) ∪ 常设赛区；政策来源不计入。"""
    store = {
        "c1": Policy(source="cnmaker-contest", source_url="c1", title="深圳大赛",
                     region="广东省深圳市"),
        "c2": Policy(source="cnmaker-contest", source_url="c2", title="云南大赛", region="云南省"),
        "c3": Policy(source="cnmaker-contest", source_url="c3", title="又一深圳大赛",
                     region="广东省深圳市"),
        "w1": _policy("w1", "无锡政策", region="江苏省无锡市新吴区"),  # 政策来源(wnd)不计入
    }
    service = PolicyService(uow_factory=make_uow_factory(policies=store))

    regions = asyncio.run(service.list_contest_regions())

    # 数据驱动地区(去重) + 常设赛区(上海/武汉)，按地区名排序、无重复
    assert regions == ["上海市", "云南省", "广东省深圳市", "湖北省武汉市"]
    assert "江苏省无锡市新吴区" not in regions  # 政策来源不计入


def test_list_contest_regions_includes_curated_when_no_data() -> None:
    """无任何赛事入库时，常设赛区(上海/武汉)仍可选，作为关注偏好预选。"""
    service = PolicyService(uow_factory=make_uow_factory(policies={}))

    regions = asyncio.run(service.list_contest_regions())

    assert regions == ["上海市", "湖北省武汉市"]


# ---------- PolicyIngestService 写 ----------

class FakeCrawler:
    def __init__(self, policies: List[Policy]) -> None:
        self._policies = policies

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        return self._policies


def test_ingest_upserts_and_vector_double_writes() -> None:
    policies_store, kb_store, kf_store, chunk_store = {}, {}, {}, {}
    factory = make_uow_factory(
        policies=policies_store, knowledge_bases=kb_store,
        knowledge_files=kf_store, document_chunks=chunk_store,
    )
    crawled = [
        _policy("u1", "政策一", body="第一条 内容。" * 50),
        _policy("u2", "政策二", body=""),  # 无正文不向量化
    ]
    service = PolicyIngestService(factory, {"wnd": FakeCrawler(crawled)}, FakeEmbedding())

    summary = asyncio.run(service.ingest("wnd", max_pages=1))

    assert summary == {
        "source": "wnd", "crawled": 2, "upserted": 2, "new": 2, "indexed": 1,
        "skipped_expired": 0, "item_type": "policy",
    }
    # 结构化表两条
    assert len(policies_store) == 2
    # 公开库已建并挂系统租户
    assert PUBLIC_KB_ID in kb_store
    assert kb_store[PUBLIC_KB_ID].tenant_id == PUBLIC_TENANT_ID
    assert kb_store[PUBLIC_KB_ID].is_public is True
    # 仅有正文的政策产生了切片
    assert len(kf_store) == 1
    assert sum(len(v) for v in chunk_store.values()) >= 1


def test_ingest_is_idempotent_on_repeat() -> None:
    policies_store, kb_store, kf_store, chunk_store = {}, {}, {}, {}
    factory = make_uow_factory(
        policies=policies_store, knowledge_bases=kb_store,
        knowledge_files=kf_store, document_chunks=chunk_store,
    )
    crawled = [_policy("u1", "政策一", body="第一条 内容。" * 50)]
    service = PolicyIngestService(factory, {"wnd": FakeCrawler(crawled)}, FakeEmbedding())

    asyncio.run(service.ingest("wnd"))
    chunks_after_first = sum(len(v) for v in chunk_store.values())
    asyncio.run(service.ingest("wnd"))  # 重复入库
    chunks_after_second = sum(len(v) for v in chunk_store.values())

    assert len(policies_store) == 1  # 结构化去重
    assert chunks_after_second == chunks_after_first  # 切片幂等替换，未翻倍


def test_crawl_run_time_takes_precedence_over_policy_crawled_at() -> None:
    """「最近更新」优先取抓取运行记录(比政策 crawled_at 更能反映真实跑过的时刻)。"""
    store = {"w1": Policy(source="wnd", source_url="w1", title="t",
                          crawled_at=datetime(2026, 6, 10, 8, 0))}
    runs = {"wnd": (datetime(2026, 7, 9, 3, 0), 0, 1)}
    service = PolicyService(
        uow_factory=make_uow_factory(policies=store, source_crawl_runs=runs)
    )

    by_key = {s.key: s for s in asyncio.run(service.list_sources_with_stats())}

    assert by_key["wnd"].last_crawled_at == datetime(2026, 7, 9, 3, 0)  # 运行记录优先
    assert by_key["wnd"].policy_count == 1  # 条数仍走政策统计


def test_ingest_records_run_so_zero_result_updates_last_crawled() -> None:
    """抓取到 0 条(全被过滤/门户无匹配)也记录运行时刻，"最近更新"不再显示"尚未抓取"。"""
    policies_store, runs = {}, {}
    factory = make_uow_factory(policies=policies_store, source_crawl_runs=runs)
    service = PolicyIngestService(factory, {"wnd-contest": FakeCrawler([])}, FakeEmbedding())

    summary = asyncio.run(service.ingest("wnd-contest", max_pages=1))
    assert summary["crawled"] == 0 and summary["new"] == 0

    read = PolicyService(uow_factory=factory)
    by_key = {s.key: s for s in asyncio.run(read.list_sources_with_stats())}

    assert by_key["wnd-contest"].policy_count == 0  # 确无入库
    assert by_key["wnd-contest"].last_crawled_at is not None  # 但已记录抓取运行
