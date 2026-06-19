"""资质条件差距分析纯函数单测(⑥ 能力② 结构化部分)。

覆盖：成立年限推导、占比推导、达标/不达标/待确认(未填) 三态、缺字段不误判为不达标、
manual_review 收口无结构化对应的概要条件、前置资质缺口。
"""

from datetime import date

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import (
    BandedCondition,
    ConditionBand,
    ConditionMetric,
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


def test_tech_sme_upper_bound_caps_via_catalog() -> None:
    """科技型中小企业(真实目录条目)的 LTE 上限：超限→不达标、未超→达标、未填→待确认。"""
    from app.infrastructure.data.qualification_catalog import load_qualification_catalog

    qual = {q.key: q for q in load_qualification_catalog()}["tech-sme"]

    big = EnterpriseProfile(total_staff=800, annual_revenue_wan=30000.0)  # 双超限
    big_checks = {c.metric: c for c in analyze_gap(big, qual).checks}
    assert big_checks[ConditionMetric.TOTAL_STAFF].status is ConditionStatus.UNMET
    assert big_checks[ConditionMetric.ANNUAL_REVENUE_WAN].status is ConditionStatus.UNMET

    small = EnterpriseProfile(total_staff=120)  # 职工达标、营收未填
    small_checks = {c.metric: c for c in analyze_gap(small, qual).checks}
    assert small_checks[ConditionMetric.TOTAL_STAFF].status is ConditionStatus.MET
    assert small_checks[ConditionMetric.ANNUAL_REVENUE_WAN].status is ConditionStatus.UNKNOWN


# ---------- 分档硬条件(banded) ----------

def _rd_invest_banded() -> BandedCondition:
    """高企口径：研发投入占比按营收三档(≤5000万→5%、5000万~2亿→4%、>2亿→3%)。"""
    return BandedCondition(
        metric=ConditionMetric.RD_INVESTMENT_RATIO,
        band_metric=ConditionMetric.ANNUAL_REVENUE_WAN,
        label="研发费用占比(分营收档)",
        bands=[
            ConditionBand(max_value=5000, threshold=5, label="≤5000万→≥5%"),
            ConditionBand(max_value=20000, threshold=4, label="5000万~2亿→≥4%"),
            ConditionBand(max_value=None, threshold=3, label=">2亿→≥3%"),
        ],
    )


def test_banded_selects_threshold_by_band_and_passes() -> None:
    """营收落中档(8000万→门槛4%)，研发投入占比 4.5% ≥ 4% → 达标。"""
    profile = EnterpriseProfile(annual_revenue_wan=8000.0, rd_investment_wan=360.0)  # 4.5%
    report = analyze_gap(profile, _qual(banded_conditions=[_rd_invest_banded()]))

    check = report.checks[0]
    assert check.threshold == 4  # 选中中档门槛
    assert check.actual == 4.5
    assert check.status is ConditionStatus.MET
    assert report.met_count == 1


def test_banded_low_band_higher_threshold_fails() -> None:
    """营收低档(3000万→门槛5%)，研发投入占比 4% < 5% → 不达标(同样占比换档结论相反)。"""
    profile = EnterpriseProfile(annual_revenue_wan=3000.0, rd_investment_wan=120.0)  # 4%
    report = analyze_gap(profile, _qual(banded_conditions=[_rd_invest_banded()]))

    check = report.checks[0]
    assert check.threshold == 5  # 低档门槛更高
    assert check.status is ConditionStatus.UNMET


def test_banded_open_top_band() -> None:
    """营收 >2亿 落开口顶档(门槛3%)，3.5% ≥ 3% → 达标。"""
    profile = EnterpriseProfile(annual_revenue_wan=50000.0, rd_investment_wan=1750.0)  # 3.5%
    report = analyze_gap(profile, _qual(banded_conditions=[_rd_invest_banded()]))

    assert report.checks[0].threshold == 3
    assert report.checks[0].status is ConditionStatus.MET


def test_banded_unknown_when_band_metric_missing() -> None:
    """没填营收 → 无法定档 → 待确认(绝不误报不达标)，即便研发投入占比已可算。"""
    profile = EnterpriseProfile(rd_investment_wan=100.0)  # 无营收，占比也算不出
    report = analyze_gap(profile, _qual(banded_conditions=[_rd_invest_banded()]))

    assert report.checks[0].status is ConditionStatus.UNKNOWN
    assert report.unmet_count == 0
    assert report.unknown_count == 1


def test_banded_unknown_when_metric_missing_but_band_known() -> None:
    """营收已填可定档，但研发投入未填→占比算不出 → 待确认。"""
    profile = EnterpriseProfile(annual_revenue_wan=8000.0)  # 能定档，但缺研发投入
    report = analyze_gap(profile, _qual(banded_conditions=[_rd_invest_banded()]))

    assert report.checks[0].status is ConditionStatus.UNKNOWN


def test_banded_label_excluded_from_manual_review() -> None:
    """分档条件 label 与 key_conditions 文案一致时，从 manual_review 去重。"""
    label = "研发费用占比(分营收档)"
    qual = _qual(
        key_conditions=[label, "其他人工条件"],
        banded_conditions=[_rd_invest_banded()],
    )

    report = analyze_gap(EnterpriseProfile(), qual)

    assert label not in report.manual_review
    assert "其他人工条件" in report.manual_review


def test_high_tech_enterprise_banded_from_catalog() -> None:
    """真实目录条目：高企研发费用占比分档已接入，营收分档影响结论。"""
    from app.infrastructure.data.qualification_catalog import load_qualification_catalog

    qual = {q.key: q for q in load_qualification_catalog()}["high-tech-enterprise"]
    # 营收 8000万(中档→≥4%)，研发投入 240万 = 3% < 4% → 不达标
    profile = EnterpriseProfile(annual_revenue_wan=8000.0, rd_investment_wan=240.0)

    checks = {c.metric: c for c in analyze_gap(profile, qual).checks}
    rd_invest = checks[ConditionMetric.RD_INVESTMENT_RATIO]
    assert rd_invest.threshold == 4
    assert rd_invest.status is ConditionStatus.UNMET
    # 分档条件文案已从 manual_review 去重(不与 key_conditions 重复)
    assert not any("研发费用占销售收入比例" in m for m in analyze_gap(profile, qual).manual_review)


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
