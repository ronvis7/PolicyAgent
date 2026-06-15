"""FeedService 离线单测(④ 工作台 Feed)：物化重算的新增/幂等语义、未读计数、状态流转。

复用内存级 UoW(_fakes) + 桩 PolicyMatchService(返回预置候选)，不依赖真实 DB/向量。
异步方法用 asyncio.run 驱动(与本仓库其他测试一致)。
"""

import asyncio
from datetime import date, datetime
from typing import List

from app.application.errors.exceptions import NotFoundError
from app.application.services.feed_service import FeedService
from app.domain.models.feed_item import FeedItem, FeedStatus
from app.domain.models.policy import Policy
from app.domain.models.policy_match import PolicyMatch

from ._fakes import make_uow_factory


class StubMatchService:
    """桩匹配服务：按租户返回预置候选，记录调用便于断言触发。"""

    def __init__(self, matches_by_tenant: dict) -> None:
        self._matches = matches_by_tenant
        self.calls: List[str] = []

    async def match_for_tenant(self, tenant_id: str, top_k: int = 20) -> List[PolicyMatch]:
        self.calls.append(tenant_id)
        return self._matches.get(tenant_id, [])


def _match(policy_id: str, title: str, score: float = 1.0) -> PolicyMatch:
    policy = Policy(
        id=policy_id, source_url=f"url-{policy_id}", title=title,
        region="江苏省无锡市新吴区", publish_date=date(2026, 6, 1),
    )
    return PolicyMatch(
        policy=policy, score=score, structured_score=score,
        matched_terms=["集成电路"], reasons=["命中关键词：集成电路"],
    )


def _service(matches_by_tenant: dict, feed_items: dict):
    return FeedService(
        uow_factory=make_uow_factory(feed_items=feed_items),
        match_service=StubMatchService(matches_by_tenant),
    )


def test_recompute_inserts_new_items_as_unread() -> None:
    feed: dict = {}
    service = _service({"t1": [_match("p1", "集成电路奖励"), _match("p2", "芯片扶持")]}, feed)

    result = asyncio.run(service.recompute_for_tenant("t1"))

    assert result == {"new": 2, "updated": 0}
    items = list(feed.values())
    assert len(items) == 2
    assert all(i.status == FeedStatus.UNREAD for i in items)
    assert {i.policy_id for i in items} == {"p1", "p2"}
    assert asyncio.run(service.unread_count("t1")) == 2


def test_recompute_is_idempotent_and_preserves_user_status() -> None:
    feed: dict = {}
    matches = {"t1": [_match("p1", "集成电路奖励", score=1.0)]}
    service = _service(matches, feed)

    # 首次重算：新增 unread
    asyncio.run(service.recompute_for_tenant("t1"))
    item_id = next(iter(feed.values())).id
    created = next(iter(feed.values())).created_at

    # 用户标记为已申报
    asyncio.run(service.set_status("t1", item_id, FeedStatus.APPLIED))

    # 政策快照变化(分数提升)后再次重算
    matches["t1"] = [_match("p1", "集成电路奖励(修订)", score=2.0)]
    result = asyncio.run(service.recompute_for_tenant("t1"))

    assert result == {"new": 0, "updated": 1}
    item = next(iter(feed.values()))
    # 同一条(未重复插入)、保留用户状态与 created_at
    assert len(feed) == 1
    assert item.status == FeedStatus.APPLIED
    assert item.created_at == created
    # 但计算快照已更新
    assert item.title == "集成电路奖励(修订)"
    assert item.score == 2.0
    assert asyncio.run(service.unread_count("t1")) == 0


def test_recompute_keeps_items_that_drop_out_of_candidates() -> None:
    feed: dict = {}
    matches = {"t1": [_match("p1", "政策一"), _match("p2", "政策二")]}
    service = _service(matches, feed)
    asyncio.run(service.recompute_for_tenant("t1"))

    # p2 跌出候选(可能已申报/想留存)：不应被删除
    matches["t1"] = [_match("p1", "政策一")]
    result = asyncio.run(service.recompute_for_tenant("t1"))

    assert result == {"new": 0, "updated": 1}
    assert {i.policy_id for i in feed.values()} == {"p1", "p2"}


def test_list_feed_filters_by_status_and_paginates() -> None:
    feed: dict = {}
    service = _service({"t1": [_match(f"p{i}", f"政策{i}") for i in range(5)]}, feed)
    asyncio.run(service.recompute_for_tenant("t1"))

    items, total = asyncio.run(service.list_feed("t1", status=FeedStatus.UNREAD, page=1, page_size=3))
    assert total == 5
    assert len(items) == 3

    none_applied, applied_total = asyncio.run(
        service.list_feed("t1", status=FeedStatus.APPLIED, page=1, page_size=10)
    )
    assert applied_total == 0
    assert none_applied == []


def test_mark_all_read_clears_unread() -> None:
    feed: dict = {}
    service = _service({"t1": [_match("p1", "政策一"), _match("p2", "政策二")]}, feed)
    asyncio.run(service.recompute_for_tenant("t1"))

    affected = asyncio.run(service.mark_all_read("t1"))

    assert affected == 2
    assert asyncio.run(service.unread_count("t1")) == 0
    assert all(i.status == FeedStatus.READ for i in feed.values())


def test_set_status_rejects_cross_tenant_item() -> None:
    feed: dict = {}
    service = _service({"t1": [_match("p1", "政策一")]}, feed)
    asyncio.run(service.recompute_for_tenant("t1"))
    item_id = next(iter(feed.values())).id

    # 另一租户不能改本租户的条目
    try:
        asyncio.run(service.set_status("t2", item_id, FeedStatus.IGNORED))
        assert False, "应抛出 NotFoundError"
    except NotFoundError:
        pass


def test_unread_count_is_tenant_scoped() -> None:
    feed: dict = {}
    service = _service(
        {"t1": [_match("p1", "政策一")], "t2": [_match("p2", "政策二"), _match("p3", "政策三")]},
        feed,
    )
    asyncio.run(service.recompute_for_tenant("t1"))
    asyncio.run(service.recompute_for_tenant("t2"))

    assert asyncio.run(service.unread_count("t1")) == 1
    assert asyncio.run(service.unread_count("t2")) == 2
