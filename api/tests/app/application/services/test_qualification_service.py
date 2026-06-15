"""QualificationService 离线单测(⑥)：按租户档案匹配资质目录、取详情。

复用内存级 UoW(_fakes) 的 enterprise_profile store + 注入桩目录，不依赖真实 DB。
"""

import asyncio

from app.application.services.qualification_service import QualificationService
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import Qualification, QualificationLevel

from ._fakes import make_uow_factory


def _qual(key, level, region, match_signals=None) -> Qualification:
    return Qualification(
        key=key, name=f"资质-{key}", level=level, issuer="某机构",
        category="科技创新", region=region, match_signals=match_signals or [],
        last_reviewed="2026-06-15",
    )


_CATALOG = [
    _qual("hi-tech", QualificationLevel.NATIONAL, "全国", ["芯片", "研发投入"]),
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
