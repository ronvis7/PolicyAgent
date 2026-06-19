"""ReportService 离线单测（主线尾巴：政策匹配简报组装）。

ReportService 直接吃三个服务（档案/Feed/资质），故用轻量桩替身即可，无需 UoW。
断言：政策按分降序取前 N 且剔除已忽略、资质差距逐条组装、临期项透传、空档案降级不报错。
"""

import asyncio
from datetime import date
from typing import List, Optional, Tuple

from app.application.services.report_service import (
    EXPIRING_WINDOW_DAYS,
    TOP_POLICIES,
    ReportService,
)
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType, FeedStatus
from app.domain.models.qualification import (
    Qualification,
    QualificationGapReport,
    QualificationLevel,
    QualificationMatch,
)


class StubProfileService:
    def __init__(self, profile: EnterpriseProfile) -> None:
        self._profile = profile

    async def get_profile(self, tenant_id: str) -> EnterpriseProfile:
        return self._profile


class StubFeedService:
    def __init__(self, items: List[FeedItem], expiring: List[FeedItem]) -> None:
        self._items = items
        self._expiring = expiring
        self.list_feed_calls: List[str] = []
        self.expiring_calls: List[Tuple[str, int]] = []

    async def list_feed(
        self, tenant_id: str, status=None, page: int = 1, page_size: int = 20,
    ) -> Tuple[List[FeedItem], int]:
        self.list_feed_calls.append(tenant_id)
        return list(self._items), len(self._items)

    async def list_expiring(self, tenant_id: str, within_days: int) -> List[FeedItem]:
        self.expiring_calls.append((tenant_id, within_days))
        return list(self._expiring)


class StubQualificationService:
    def __init__(
        self,
        matches: List[QualificationMatch],
        gaps_by_key: dict,
    ) -> None:
        self._matches = matches
        self._gaps = gaps_by_key

    async def match_for_tenant(self, tenant_id: str, top_k: int = 50) -> List[QualificationMatch]:
        return list(self._matches)

    async def analyze_gap_for_tenant(
        self, tenant_id: str, key: str,
    ) -> Optional[QualificationGapReport]:
        return self._gaps.get(key)


def _policy_item(policy_id: str, score: float, status: FeedStatus = FeedStatus.UNREAD) -> FeedItem:
    return FeedItem(
        tenant_id="t1", type=FeedItemType.POLICY, policy_id=policy_id,
        title=f"政策-{policy_id}", score=score, status=status,
    )


def _qmatch(key: str) -> QualificationMatch:
    qual = Qualification(key=key, name=f"资质-{key}", level=QualificationLevel.NATIONAL)
    return QualificationMatch(qualification=qual, score=0.9, eligible=True)


def _gap(key: str) -> QualificationGapReport:
    qual = Qualification(key=key, name=f"资质-{key}", level=QualificationLevel.NATIONAL)
    return QualificationGapReport(qualification=qual, summary="差一项")


def _build(profile, items, expiring, matches, gaps) -> ReportService:
    return ReportService(
        profile_service=StubProfileService(profile),
        feed_service=StubFeedService(items, expiring),
        qualification_service=StubQualificationService(matches, gaps),
    )


def test_build_brief_sorts_policies_by_score_and_excludes_ignored():
    profile = EnterpriseProfile(tenant_id="t1", company_name="测试公司")
    items = [
        _policy_item("low", 0.2),
        _policy_item("high", 0.9),
        _policy_item("ignored", 0.99, status=FeedStatus.IGNORED),
        _policy_item("mid", 0.5),
    ]
    service = _build(profile, items, [], [], {})

    report = asyncio.run(service.build_brief("t1"))

    ids = [p.policy_id for p in report.matched_policies]
    assert ids == ["high", "mid", "low"]  # 已忽略剔除、按分降序
    assert report.profile.company_name == "测试公司"
    assert report.disclaimer  # 免责声明在位


def test_build_brief_excludes_non_policy_feed_items():
    profile = EnterpriseProfile(tenant_id="t1")
    qual_item = FeedItem(
        tenant_id="t1", type=FeedItemType.QUALIFICATION, policy_id="q", title="资质条目", score=1.0,
    )
    items = [_policy_item("p1", 0.5), qual_item]
    service = _build(profile, items, [], [], {})

    report = asyncio.run(service.build_brief("t1"))

    assert [p.policy_id for p in report.matched_policies] == ["p1"]


def test_build_brief_assembles_qualification_gaps_in_match_order():
    profile = EnterpriseProfile(tenant_id="t1")
    matches = [_qmatch("high-tech"), _qmatch("tech-sme")]
    gaps = {"high-tech": _gap("high-tech"), "tech-sme": _gap("tech-sme")}
    service = _build(profile, [], [], matches, gaps)

    report = asyncio.run(service.build_brief("t1"))

    keys = [g.qualification.key for g in report.qualification_gaps]
    assert keys == ["high-tech", "tech-sme"]


def test_build_brief_drops_gaps_with_no_report():
    profile = EnterpriseProfile(tenant_id="t1")
    matches = [_qmatch("known"), _qmatch("missing")]
    gaps = {"known": _gap("known")}  # missing 无差距报告 → 应被丢弃
    service = _build(profile, [], [], matches, gaps)

    report = asyncio.run(service.build_brief("t1"))

    assert [g.qualification.key for g in report.qualification_gaps] == ["known"]


def test_build_brief_passes_expiring_window():
    profile = EnterpriseProfile(tenant_id="t1")
    expiring = [_policy_item("soon", 0.5)]
    feed = StubFeedService([], expiring)
    service = ReportService(
        profile_service=StubProfileService(profile),
        feed_service=feed,
        qualification_service=StubQualificationService([], {}),
    )

    report = asyncio.run(service.build_brief("t1"))

    assert [e.policy_id for e in report.expiring] == ["soon"]
    assert feed.expiring_calls == [("t1", EXPIRING_WINDOW_DAYS)]


def test_build_brief_empty_profile_degrades_gracefully():
    profile = EnterpriseProfile(tenant_id="t1")  # 空档案
    service = _build(profile, [], [], [], {})

    report = asyncio.run(service.build_brief("t1"))

    assert report.matched_policies == []
    assert report.qualification_gaps == []
    assert report.expiring == []


def test_build_brief_caps_policies_at_top_n():
    profile = EnterpriseProfile(tenant_id="t1")
    items = [_policy_item(f"p{i}", score=float(i)) for i in range(TOP_POLICIES + 5)]
    service = _build(profile, items, [], [], {})

    report = asyncio.run(service.build_brief("t1"))

    assert len(report.matched_policies) == TOP_POLICIES
