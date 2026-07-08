"""FeedService 离线单测(④ 工作台 Feed)：物化重算的新增/幂等语义、未读计数、状态流转。

复用内存级 UoW(_fakes) + 桩 PolicyMatchService(返回预置候选)，不依赖真实 DB/向量。
异步方法用 asyncio.run 驱动(与本仓库其他测试一致)。
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import List

from app.application.errors.exceptions import NotFoundError
from app.application.services.feed_service import FeedService
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType, FeedStatus
from app.domain.models.policy import Policy
from app.domain.models.policy_match import PolicyMatch
from app.domain.models.qualification import (
    Qualification,
    QualificationLevel,
    QualificationMatch,
)

from ._fakes import make_uow_factory


class StubMatchService:
    """桩匹配服务：按租户返回预置候选，记录调用便于断言触发。"""

    def __init__(self, matches_by_tenant: dict) -> None:
        self._matches = matches_by_tenant
        self.calls: List[str] = []

    async def match_for_tenant(self, tenant_id: str, top_k: int = 20) -> List[PolicyMatch]:
        self.calls.append(tenant_id)
        return self._matches.get(tenant_id, [])


def _match(
    policy_id: str, title: str, score: float = 1.0, source: str = "wnd",
    region: str = "江苏省无锡市新吴区",
) -> PolicyMatch:
    policy = Policy(
        id=policy_id, source=source, source_url=f"url-{policy_id}", title=title,
        region=region, publish_date=date(2026, 6, 1),
    )
    return PolicyMatch(
        policy=policy, score=score, structured_score=score,
        matched_terms=["集成电路"], reasons=["命中关键词：集成电路"],
    )


class StubQualificationService:
    """桩资质匹配服务：按租户返回预置资质候选。"""

    def __init__(self, matches_by_tenant: dict) -> None:
        self._matches = matches_by_tenant
        self.calls: List[str] = []

    async def match_for_tenant(self, tenant_id: str, top_k: int = 50) -> List[QualificationMatch]:
        self.calls.append(tenant_id)
        return self._matches.get(tenant_id, [])


def _qmatch(key: str, name: str, eligible: bool = True, score: float = 1.0) -> QualificationMatch:
    qual = Qualification(
        key=key, name=name, level=QualificationLevel.NATIONAL, region="全国",
        issuer="科技部", last_reviewed="2026-06-15",
    )
    return QualificationMatch(
        qualification=qual, score=score, eligible=eligible,
        matched_signals=["集成电路"], reasons=["可申报", "符合：集成电路"],
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


def test_recompute_folds_qualifications_into_feed() -> None:
    feed: dict = {}
    service = FeedService(
        uow_factory=make_uow_factory(feed_items=feed),
        match_service=StubMatchService({"t1": [_match("p1", "集成电路奖励")]}),
        qualification_service=StubQualificationService({"t1": [_qmatch("hi-tech", "高新技术企业认定")]}),
    )

    result = asyncio.run(service.recompute_for_tenant("t1"))

    # 政策 + 资质各 1 条都进 Feed
    assert result == {"new": 2, "updated": 0}
    items = {i.policy_id: i for i in feed.values()}
    assert set(items) == {"p1", "hi-tech"}

    qual_item = items["hi-tech"]
    assert qual_item.type == FeedItemType.QUALIFICATION
    assert qual_item.title == "高新技术企业认定"
    assert qual_item.issuer == "科技部"
    assert qual_item.region == "全国"
    assert qual_item.status == FeedStatus.UNREAD
    assert qual_item.matched_terms == ["集成电路"]
    assert "可申报" in qual_item.reasons

    policy_item = items["p1"]
    assert policy_item.type == FeedItemType.POLICY


def test_recompute_marks_contest_source_items_as_competition() -> None:
    """赛事来源(competition_sources)的候选打 type=competition，政策来源不受影响。"""
    feed: dict = {}
    service = FeedService(
        uow_factory=make_uow_factory(feed_items=feed),
        match_service=StubMatchService({"t1": [
            _match("c1", "创新创业大赛申报通知", source="wnd-contest"),
            _match("p1", "集成电路奖励", source="wnd"),
        ]}),
        competition_sources={"wnd-contest", "gxt-contest"},
    )

    result = asyncio.run(service.recompute_for_tenant("t1"))

    assert result == {"new": 2, "updated": 0}
    items = {i.policy_id: i for i in feed.values()}
    assert items["c1"].type == FeedItemType.COMPETITION
    assert items["c1"].title == "创新创业大赛申报通知"
    assert items["p1"].type == FeedItemType.POLICY


def test_recompute_without_competition_sources_defaults_to_policy() -> None:
    """未配置赛事来源(缺省)时全部保持 policy 类型，向后兼容。"""
    feed: dict = {}
    service = _service({"t1": [_match("c1", "大赛通知", source="wnd-contest")]}, feed)

    asyncio.run(service.recompute_for_tenant("t1"))

    assert all(i.type == FeedItemType.POLICY for i in feed.values())


def test_recompute_preserves_competition_type_on_snapshot_update() -> None:
    """重算更新快照时 competition 类型不被冲掉(with_snapshot_from 不动 type，但新快照同类型)。"""
    feed: dict = {}
    matches = {"t1": [_match("c1", "大赛通知", source="wnd-contest")]}
    service = FeedService(
        uow_factory=make_uow_factory(feed_items=feed),
        match_service=StubMatchService(matches),
        competition_sources={"wnd-contest"},
    )
    asyncio.run(service.recompute_for_tenant("t1"))
    matches["t1"] = [_match("c1", "大赛通知(延期)", source="wnd-contest")]

    result = asyncio.run(service.recompute_for_tenant("t1"))

    assert result == {"new": 0, "updated": 1}
    item = next(iter(feed.values()))
    assert item.type == FeedItemType.COMPETITION
    assert item.title == "大赛通知(延期)"


def _contest_service(matches_by_tenant: dict, feed: dict, profiles: dict) -> FeedService:
    return FeedService(
        uow_factory=make_uow_factory(feed_items=feed, enterprise_profiles=profiles),
        match_service=StubMatchService(matches_by_tenant),
        competition_sources={"wnd-contest", "gxt-contest", "cq-contest"},
    )


def test_recompute_filters_competition_by_contest_regions() -> None:
    """档案选了参赛关注地区：地区外的赛事不物化进 Feed，政策条目不受影响。"""
    feed: dict = {}
    profiles = {"t1": EnterpriseProfile(tenant_id="t1", contest_regions=["江苏省"])}
    service = _contest_service({"t1": [
        _match("c-js", "江苏大赛", source="gxt-contest", region="江苏省"),
        _match("c-cq", "重庆大赛", source="cq-contest", region="重庆市"),
        _match("p-cq", "重庆政策", source="cq", region="重庆市"),  # 政策不走关注地区
    ]}, feed, profiles)

    asyncio.run(service.recompute_for_tenant("t1"))

    assert {i.policy_id for i in feed.values()} == {"c-js", "p-cq"}


def test_recompute_contest_regions_empty_means_no_limit() -> None:
    """未选关注地区(或未建档)：赛事不按地区过滤，全部物化。"""
    feed: dict = {}
    service = _contest_service({"t1": [
        _match("c-cq", "重庆大赛", source="cq-contest", region="重庆市"),
    ]}, feed, profiles={})  # 无档案

    asyncio.run(service.recompute_for_tenant("t1"))

    assert {i.policy_id for i in feed.values()} == {"c-cq"}


def test_recompute_contest_regions_hierarchical() -> None:
    """选区县也命中其省级赛事(省赛可参加)。"""
    feed: dict = {}
    profiles = {"t1": EnterpriseProfile(
        tenant_id="t1", contest_regions=["江苏省无锡市新吴区"],
    )}
    service = _contest_service({"t1": [
        _match("c-province", "省级大赛", source="gxt-contest", region="江苏省"),
        _match("c-sh", "上海大赛", source="wnd-contest", region="上海市杨浦区"),
    ]}, feed, profiles)

    asyncio.run(service.recompute_for_tenant("t1"))

    assert {i.policy_id for i in feed.values()} == {"c-province"}


def test_recompute_without_qualification_service_only_does_policies() -> None:
    feed: dict = {}
    service = _service({"t1": [_match("p1", "政策一")]}, feed)

    result = asyncio.run(service.recompute_for_tenant("t1"))

    assert result == {"new": 1, "updated": 0}
    assert all(i.type == FeedItemType.POLICY for i in feed.values())


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


def _match_with_deadline(
    policy_id: str, title: str, deadline: date, deadline_status: str = "extracted",
) -> PolicyMatch:
    policy = Policy(
        id=policy_id, source_url=f"url-{policy_id}", title=title,
        region="江苏省无锡市新吴区", publish_date=date(2026, 6, 1),
        apply_deadline=deadline if deadline_status == "extracted" else None,
        deadline_status=deadline_status,
    )
    return PolicyMatch(policy=policy, score=1.0, structured_score=1.0)


def test_recompute_carries_deadline_snapshot_to_feed() -> None:
    feed: dict = {}
    dl = date.today() + timedelta(days=5)
    service = _service({"t1": [_match_with_deadline("p1", "高企申报", dl)]}, feed)

    asyncio.run(service.recompute_for_tenant("t1"))

    item = next(iter(feed.values()))
    assert item.apply_deadline == dl
    assert item.deadline_status == "extracted"


def test_list_expiring_returns_only_extracted_within_window_sorted() -> None:
    feed: dict = {}
    today = date.today()
    matches = {"t1": [
        _match_with_deadline("p-soon", "5天后截止", today + timedelta(days=5)),
        _match_with_deadline("p-later", "3天后截止", today + timedelta(days=3)),
        _match_with_deadline("p-far", "30天后截止", today + timedelta(days=30)),
        _match_with_deadline("p-rolling", "常年受理", today, deadline_status="rolling"),
        _match_with_deadline("p-unknown", "无截止", today, deadline_status="unknown"),
    ]}
    service = _service(matches, feed)
    asyncio.run(service.recompute_for_tenant("t1"))

    expiring = asyncio.run(service.list_expiring("t1", within_days=14))

    # 仅 extracted 且落在 14 天内；按截止升序(最紧的在前)
    assert [i.policy_id for i in expiring] == ["p-later", "p-soon"]


def test_list_expiring_excludes_ignored() -> None:
    feed: dict = {}
    dl = date.today() + timedelta(days=2)
    service = _service({"t1": [_match_with_deadline("p1", "临期政策", dl)]}, feed)
    asyncio.run(service.recompute_for_tenant("t1"))
    item_id = next(iter(feed.values())).id
    asyncio.run(service.set_status("t1", item_id, FeedStatus.IGNORED))

    assert asyncio.run(service.list_expiring("t1", within_days=14)) == []


def test_list_expiring_is_tenant_scoped() -> None:
    feed: dict = {}
    dl = date.today() + timedelta(days=3)
    service = _service(
        {"t1": [_match_with_deadline("p1", "t1政策", dl)],
         "t2": [_match_with_deadline("p2", "t2政策", dl)]},
        feed,
    )
    asyncio.run(service.recompute_for_tenant("t1"))
    asyncio.run(service.recompute_for_tenant("t2"))

    t1_expiring = asyncio.run(service.list_expiring("t1", within_days=14))
    assert [i.policy_id for i in t1_expiring] == ["p1"]


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


def test_recompute_drops_expired_competition() -> None:
    """截止已过的赛事=失效机会，不物化进工作台；无截止/未过期的保留，政策不受影响。"""
    feed: dict = {}
    today = date.today()

    expired = _match("c-old", "已截止大赛", source="gxt-contest", region="江苏省")
    expired.policy.apply_deadline = today - timedelta(days=1)
    open_ = _match("c-open", "报名中大赛", source="gxt-contest", region="江苏省")
    open_.policy.apply_deadline = today + timedelta(days=30)
    undated = _match("c-unknown", "未知截止大赛", source="gxt-contest", region="江苏省")
    stale_policy = _match("p-old", "历史政策", source="wnd")
    stale_policy.policy.apply_deadline = today - timedelta(days=1)  # 政策过期仍展示

    service = _contest_service(
        {"t1": [expired, open_, undated, stale_policy]}, feed, profiles={},
    )

    asyncio.run(service.recompute_for_tenant("t1"))

    assert {i.policy_id for i in feed.values()} == {"c-open", "c-unknown", "p-old"}
