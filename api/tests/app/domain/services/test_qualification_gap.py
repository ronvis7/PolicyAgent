"""资质条件差距分析纯函数单测(⑥ 能力② 结构化部分)。

覆盖：成立年限推导、占比推导、达标/不达标/待确认(未填) 三态、缺字段不误判为不达标、
manual_review 收口无结构化对应的概要条件、前置资质缺口。
"""

from datetime import date

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import (
    ConditionMetric,
    ConditionOperator,
    ConditionStatus,
    Qualification,
    QualificationCondition,
    QualificationLevel,
)
from app.domain.services.qualification_gap import analyze_gap, company_age_years


def _qual(**kwargs) -> Qualification:
    base = dict(key="k", name="测试资质", level=QualificationLevel.NATIONAL)
    base.update(kwargs)
    return Qualification(**base)


def test_company_age_years_from_date() -> None:
    assert company_age_years("2019-06-01", date(2026, 6, 16)) == 7
    assert company_age_years("2019-06-01", date(2020, 1, 1)) == 0  # 不满1年
    assert company_age_years("2019", date(2026, 1, 1)) == 7  # 只到年
    assert company_age_years("", date(2026, 1, 1)) is None  # 未填
    assert company_age_years("乱填", date(2026, 1, 1)) is None


def test_met_unmet_unknown_three_states() -> None:
    profile = EnterpriseProfile(
        established_date="2019-06-01",  # 满7年 → 达标
        total_staff=100,
        rd_staff=8,  # 占比 8% < 10% → 不达标
        # 注册资本未填 → 待确认
    )
    qual = _qual(
        structured_conditions=[
            QualificationCondition(metric=ConditionMetric.COMPANY_AGE_YEARS, threshold=1, label="成立满1年"),
            QualificationCondition(metric=ConditionMetric.RD_STAFF_RATIO, threshold=10, label="研发人员占比≥10%"),
            QualificationCondition(metric=ConditionMetric.REGISTERED_CAPITAL_WAN, threshold=500, label="注册资本≥500万"),
        ],
    )

    report = analyze_gap(profile, qual, today=date(2026, 6, 16))

    by_metric = {c.metric: c for c in report.checks}
    assert by_metric[ConditionMetric.COMPANY_AGE_YEARS].status is ConditionStatus.MET
    assert by_metric[ConditionMetric.RD_STAFF_RATIO].status is ConditionStatus.UNMET
    assert by_metric[ConditionMetric.RD_STAFF_RATIO].actual == 8.0
    assert by_metric[ConditionMetric.REGISTERED_CAPITAL_WAN].status is ConditionStatus.UNKNOWN
    assert by_metric[ConditionMetric.REGISTERED_CAPITAL_WAN].actual is None
    assert report.met_count == 1
    assert report.unmet_count == 1
    assert report.unknown_count == 1


def test_missing_field_is_unknown_not_unmet() -> None:
    """档案没填研发投入 → 待确认，绝不能判成不达标"""
    profile = EnterpriseProfile(annual_revenue_wan=8000.0)  # 有营收但没研发投入
    qual = _qual(
        structured_conditions=[
            QualificationCondition(metric=ConditionMetric.RD_INVESTMENT_RATIO, threshold=3, label="研发投入占比≥3%"),
        ],
    )

    report = analyze_gap(profile, qual)

    assert report.checks[0].status is ConditionStatus.UNKNOWN
    assert report.unmet_count == 0
    assert report.unknown_count == 1


def test_ratio_derivation() -> None:
    profile = EnterpriseProfile(annual_revenue_wan=10000.0, rd_investment_wan=500.0)  # 5%
    qual = _qual(
        structured_conditions=[
            QualificationCondition(metric=ConditionMetric.RD_INVESTMENT_RATIO, threshold=3, label="研发投入≥3%"),
        ],
    )

    report = analyze_gap(profile, qual)

    assert report.checks[0].actual == 5.0
    assert report.checks[0].status is ConditionStatus.MET


def test_ip_total_sums_components() -> None:
    profile = EnterpriseProfile(invention_patents=2, other_ip_count=10)
    qual = _qual(
        structured_conditions=[
            QualificationCondition(metric=ConditionMetric.IP_TOTAL, threshold=5, label="知识产权≥5件"),
        ],
    )

    report = analyze_gap(profile, qual)

    assert report.checks[0].actual == 12.0
    assert report.checks[0].status is ConditionStatus.MET


def test_manual_review_collects_unstructured_conditions() -> None:
    """key_conditions 中无结构化对应的，进 manual_review 待人工/材料确认"""
    qual = _qual(
        key_conditions=["成立满1年", "拥有核心自主知识产权", "属国家重点支持高新技术领域"],
        structured_conditions=[
            QualificationCondition(metric=ConditionMetric.COMPANY_AGE_YEARS, threshold=1, label="成立满1年"),
        ],
    )

    report = analyze_gap(EnterpriseProfile(established_date="2019-01-01"), qual, today=date(2026, 1, 1))

    assert "成立满1年" not in report.manual_review  # 已结构化，不重复
    assert "拥有核心自主知识产权" in report.manual_review
    assert "属国家重点支持高新技术领域" in report.manual_review


def test_missing_prerequisites_reported() -> None:
    qual = _qual(prerequisites=["江苏省专精特新中小企业"])
    profile = EnterpriseProfile(qualifications=["高新技术企业"])

    report = analyze_gap(profile, qual)

    assert report.prerequisites_missing == ["江苏省专精特新中小企业"]


def test_held_prerequisite_not_reported() -> None:
    qual = _qual(prerequisites=["江苏省专精特新中小企业"])
    profile = EnterpriseProfile(qualifications=["江苏省专精特新中小企业", "高新技术企业"])

    report = analyze_gap(profile, qual)

    assert report.prerequisites_missing == []
