"""QualificationService 离线单测(⑥)：按租户档案匹配资质目录、取详情。

复用内存级 UoW(_fakes) 的 enterprise_profile store + 注入桩目录，不依赖真实 DB。
"""

import asyncio

from app.application.services.qualification_service import QualificationService
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import (
    ConditionMetric,
    ConditionStatus,
    Qualification,
    QualificationCondition,
    QualificationLevel,
)

from ._fakes import make_uow_factory


def _qual(key, level, region, match_signals=None, **extra) -> Qualification:
    return Qualification(
        key=key, name=f"资质-{key}", level=level, issuer="某机构",
        category="科技创新", region=region, match_signals=match_signals or [],
        last_reviewed="2026-06-15", **extra,
    )


_CATALOG = [
    _qual(
        "hi-tech", QualificationLevel.NATIONAL, "全国", ["芯片", "研发投入"],
        key_conditions=["注册成立满1年", "拥有核心自主知识产权"],
        structured_conditions=[
            QualificationCondition(
                metric=ConditionMetric.RD_STAFF_RATIO, threshold=10, label="研发人员占比≥10%",
            ),
        ],
    ),
    _qual("js-sxt", QualificationLevel.PROVINCIAL, "江苏省", ["芯片"]),
    _qual("gd-only", QualificationLevel.PROVINCIAL, "广东省", ["芯片"]),
]


def _service(profiles: dict) -> QualificationService:
    return QualificationService(
        uow_factory=make_uow_factory(enterprise_profiles=profiles),
        catalog=_CATALOG,
    )


def test_match_for_tenant_excludes_other_region_and_ranks_eligible_first() -> None:
    profile = EnterpriseProfile(
        tenant_id="t1", province="江苏省", city="无锡市", district="新吴区",
        keywords=["芯片", "研发投入"],
    )
    service = _service({"t1": profile})

    results = asyncio.run(service.match_for_tenant("t1"))

    keys = [m.qualification.key for m in results]
    assert "gd-only" not in keys  # 广东省资质对江苏档案不适用
    assert keys[0] == "hi-tech"  # 全覆盖 → 可申报排最前
    assert results[0].eligible is True


def test_match_for_tenant_returns_empty_when_no_profile() -> None:
    service = _service({})

    results = asyncio.run(service.match_for_tenant("nobody"))

    assert results == []


def test_match_for_tenant_respects_top_k() -> None:
    profile = EnterpriseProfile(
        tenant_id="t1", province="江苏省", city="无锡市", district="新吴区",
        keywords=["芯片"],
    )
    service = _service({"t1": profile})

    results = asyncio.run(service.match_for_tenant("t1", top_k=1))

    assert len(results) == 1


def test_get_by_key_returns_detail_or_none() -> None:
    service = _service({})

    found = service.get_by_key("hi-tech")
    missing = service.get_by_key("does-not-exist")

    assert found is not None
    assert found.name == "资质-hi-tech"
    assert missing is None


def test_analyze_gap_uses_tenant_profile() -> None:
    """有档案时按档案核验结构化硬条件(研发人员占比 8% < 10% → 不达标)"""
    profile = EnterpriseProfile(tenant_id="t1", total_staff=100, rd_staff=8)
    service = _service({"t1": profile})

    report = asyncio.run(service.analyze_gap_for_tenant("t1", "hi-tech"))

    assert report is not None
    assert report.checks[0].status is ConditionStatus.UNMET
    assert "拥有核心自主知识产权" in report.manual_review  # 无结构化对应 → 人工确认


def test_analyze_gap_without_profile_is_all_unknown() -> None:
    """无档案 → 不报空，硬条件判为待确认，引导先完善档案"""
    service = _service({})

    report = asyncio.run(service.analyze_gap_for_tenant("nobody", "hi-tech"))

    assert report is not None
    assert report.checks[0].status is ConditionStatus.UNKNOWN
    assert report.unknown_count == 1


def test_analyze_gap_returns_none_for_unknown_key() -> None:
    service = _service({})

    assert asyncio.run(service.analyze_gap_for_tenant("t1", "does-not-exist")) is None
