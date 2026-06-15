"""资质 matcher 纯函数单测(⑥ 能力①：企业档案 × 资质目录)。

覆盖：地区适用门槛、信号重合打分、前置资质缺失、可申报/接近判定、排序。
无 IO，直接构造档案与资质对象。
"""

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale
from app.domain.models.qualification import Qualification, QualificationLevel
from app.domain.services.qualification_matcher import (
    match_qualification,
    match_qualifications,
    region_applies,
)


def _qual(
    key: str,
    level: QualificationLevel,
    region: str,
    match_signals=None,
    prerequisites=None,
) -> Qualification:
    return Qualification(
        key=key,
        name=f"资质-{key}",
        level=level,
        issuer="某机构",
        category="科技创新",
        region=region,
        match_signals=match_signals or [],
        prerequisites=prerequisites or [],
        last_reviewed="2026-06-15",
    )


def _profile(**kwargs) -> EnterpriseProfile:
    base = dict(
        tenant_id="t1",
        province="江苏省",
        city="无锡市",
        district="新吴区",
        industry="高新技术",
        tech_domains=["集成电路"],
        keywords=["芯片"],
        qualifications=[],
    )
    base.update(kwargs)
    return EnterpriseProfile(**base)


def test_national_and_general_always_apply_regardless_of_region() -> None:
    profile = _profile(province="重庆市", city="重庆市", district="渝北区")
    national = _qual("hi-tech", QualificationLevel.NATIONAL, "全国")
    general = _qual("iso9001", QualificationLevel.GENERAL, "全国")

    assert region_applies(profile, national) is True
    assert region_applies(profile, general) is True


def test_provincial_applies_only_to_matching_province() -> None:
    js = _qual("js-sxt", QualificationLevel.PROVINCIAL, "江苏省")
    jiangsu = _profile(province="江苏省")
    chongqing = _profile(province="重庆市", city="重庆市", district="渝北区")

    assert region_applies(jiangsu, js) is True
    assert region_applies(chongqing, js) is False


def test_municipal_applies_when_city_or_district_overlaps() -> None:
    wx = _qual("wx-center", QualificationLevel.MUNICIPAL, "无锡市")
    xinwu = _qual("xw-bonus", QualificationLevel.MUNICIPAL, "无锡市新吴区")
    profile = _profile(city="无锡市", district="新吴区")
    other = _profile(city="苏州市", district="工业园区", province="江苏省")

    assert region_applies(profile, wx) is True
    assert region_applies(profile, xinwu) is True
    assert region_applies(other, wx) is False


def test_match_qualification_returns_none_when_region_not_applicable() -> None:
    chongqing = _profile(province="重庆市", city="重庆市", district="渝北区")
    js = _qual("js-sxt", QualificationLevel.PROVINCIAL, "江苏省", match_signals=["芯片"])

    assert match_qualification(chongqing, js) is None


def test_eligible_when_signals_covered_and_no_missing_prerequisites() -> None:
    profile = _profile(qualifications=["高新技术企业"], keywords=["芯片", "研发投入"])
    qual = _qual(
        "xjt",
        QualificationLevel.NATIONAL,
        "全国",
        match_signals=["芯片", "研发投入"],
        prerequisites=["高新技术企业"],
    )

    result = match_qualification(profile, qual)

    assert result is not None
    assert result.eligible is True
    assert set(result.matched_signals) == {"芯片", "研发投入"}
    assert result.missing_signals == []
    assert result.missing_prerequisites == []
    assert result.score > 0


def test_near_eligible_when_prerequisite_missing() -> None:
    profile = _profile(qualifications=[], keywords=["芯片"])
    qual = _qual(
        "xiaojuren",
        QualificationLevel.NATIONAL,
        "全国",
        match_signals=["芯片"],
        prerequisites=["省级专精特新中小企业"],
    )

    result = match_qualification(profile, qual)

    assert result is not None
    assert result.eligible is False  # 前置资质缺失 → 不可直接申报
    assert result.missing_prerequisites == ["省级专精特新中小企业"]


def test_near_eligible_when_signal_coverage_low() -> None:
    profile = _profile(keywords=["芯片"], tech_domains=[], industry="")
    qual = _qual(
        "many-signals",
        QualificationLevel.NATIONAL,
        "全国",
        match_signals=["芯片", "生物医药", "新材料", "高端装备", "节能环保"],
    )

    result = match_qualification(profile, qual)

    assert result is not None
    assert result.eligible is False  # 覆盖率过低
    assert "芯片" in result.matched_signals
    assert len(result.missing_signals) == 4


def test_match_qualifications_sorts_eligible_first_then_score() -> None:
    profile = _profile(
        qualifications=["高新技术企业"], keywords=["芯片", "研发投入"], industry="高新技术",
    )
    catalog = [
        _qual("low", QualificationLevel.NATIONAL, "全国",
              match_signals=["生物医药", "新材料", "节能环保"]),  # 覆盖率低 → near
        _qual("high", QualificationLevel.NATIONAL, "全国",
              match_signals=["芯片", "研发投入"]),  # 全覆盖 → eligible
        _qual("other-region", QualificationLevel.PROVINCIAL, "广东省",
              match_signals=["芯片"]),  # 地区不适用 → 排除
    ]

    results = match_qualifications(profile, catalog)

    keys = [m.qualification.key for m in results]
    assert "other-region" not in keys  # 地区不适用被排除
    assert keys[0] == "high"  # 可申报排最前
    assert results[0].eligible is True
