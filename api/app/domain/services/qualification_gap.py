"""企业档案 × 资质硬条件的差距分析（主线⑥ 能力② 的纯函数内核，无 IO）。

混合引擎的**结构化部分**：把资质 `structured_conditions` 里能由档案数值确定性核验的硬条件
逐条算成 达标/不达标/待确认(未填)；无结构化对应的 `key_conditions` 收口到 manual_review，
交后续材料指引(能力③, Agent)或人工确认。前置资质缺口复用能力① 的子串判定。

风险纪律：门槛数值仍为结构性概要(见 Qualification.disclaimer)，本模块只做"档案值 vs 概要门槛"
的机械比对，不构成权威结论；缺字段一律判"待确认"，绝不误报"不达标"。
"""

from datetime import date
from typing import List, Optional

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import (
    BandedCondition,
    ConditionBand,
    ConditionCheck,
    ConditionMetric,
    ConditionOperator,
    ConditionStatus,
    Qualification,
    QualificationCondition,
    QualificationGapReport,
)


def company_age_years(established_date: str, today: Optional[date] = None) -> Optional[int]:
    """由成立日期(YYYY / YYYY-MM / YYYY-MM-DD)推导整年龄；空或非法返回 None。"""
    value = (established_date or "").strip()
    if not value:
        return None
    parts = value.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        start = date(year, month, day)
    except (ValueError, IndexError):
        return None

    ref = today or date.today()
    if start > ref:
        return None
    years = ref.year - start.year - ((ref.month, ref.day) < (start.month, start.day))
    return max(0, years)


def _actual_value(
    profile: EnterpriseProfile, metric: ConditionMetric, today: Optional[date],
) -> Optional[float]:
    """从档案推导某指标的实际值；所需字段缺失返回 None(=待确认)。"""
    if metric is ConditionMetric.COMPANY_AGE_YEARS:
        age = company_age_years(profile.established_date, today)
        return float(age) if age is not None else None
    if metric is ConditionMetric.TOTAL_STAFF:
        return _as_float(profile.total_staff)
    if metric is ConditionMetric.RD_STAFF:
        return _as_float(profile.rd_staff)
    if metric is ConditionMetric.RD_STAFF_RATIO:
        return _ratio(profile.rd_staff, profile.total_staff)
    if metric is ConditionMetric.RD_INVESTMENT_RATIO:
        return _ratio(profile.rd_investment_wan, profile.annual_revenue_wan)
    if metric is ConditionMetric.INVENTION_PATENTS:
        return _as_float(profile.invention_patents)
    if metric is ConditionMetric.IP_TOTAL:
        return _ip_total(profile)
    if metric is ConditionMetric.REGISTERED_CAPITAL_WAN:
        return _as_float(profile.registered_capital_wan)
    if metric is ConditionMetric.ANNUAL_REVENUE_WAN:
        return _as_float(profile.annual_revenue_wan)
    return None


def _as_float(value: Optional[float]) -> Optional[float]:
    return float(value) if value is not None else None


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """占比(%)，分子或分母缺失/分母为0时返回 None(待确认)。"""
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 1)


def _ip_total(profile: EnterpriseProfile) -> Optional[float]:
    """知识产权总数；两项均未填为 None，任一已填则缺项按 0 计入。"""
    if profile.invention_patents is None and profile.other_ip_count is None:
        return None
    return float((profile.invention_patents or 0) + (profile.other_ip_count or 0))


def _evaluate(
    profile: EnterpriseProfile, condition: QualificationCondition, today: Optional[date],
) -> ConditionCheck:
    actual = _actual_value(profile, condition.metric, today)
    if actual is None:
        status = ConditionStatus.UNKNOWN
        detail = f"{condition.label or condition.metric.value}：档案未填写，待确认"
    else:
        if condition.op is ConditionOperator.GTE:
            met = actual >= condition.threshold
        else:
            met = actual <= condition.threshold
        status = ConditionStatus.MET if met else ConditionStatus.UNMET
        sign = "≥" if condition.op is ConditionOperator.GTE else "≤"
        verdict = "达标" if met else "不达标"
        detail = f"{condition.label or condition.metric.value}：实际 {_fmt(actual)}，要求 {sign} {_fmt(condition.threshold)}（{verdict}）"
    return ConditionCheck(
        metric=condition.metric,
        op=condition.op,
        threshold=condition.threshold,
        label=condition.label,
        actual=actual,
        status=status,
        detail=detail,
    )


def _fmt(value: float) -> str:
    """整数去掉小数尾巴，便于展示。"""
    return str(int(value)) if float(value).is_integer() else str(value)


def _resolve_band(bands: List[ConditionBand], band_value: float) -> Optional[ConditionBand]:
    """按落档值选中适用档：升序逐档，首个 band_value ≤ max_value 命中；max_value=None 为开口顶档。"""
    for band in bands:
        if band.max_value is None or band_value <= band.max_value:
            return band
    return None


def _evaluate_banded(
    profile: EnterpriseProfile, banded: BandedCondition, today: Optional[date],
) -> ConditionCheck:
    """分档硬条件核验：先按 band_metric 定档，再比被核验指标；任一所需字段缺失→待确认。"""
    label = banded.label or banded.metric.value
    band_value = _actual_value(profile, banded.band_metric, today)
    if band_value is None:
        return _banded_unknown(banded, f"{label}：需先确定分档依据，待确认")

    band = _resolve_band(banded.bands, band_value)
    if band is None:  # 目录档位未覆盖该取值(异常配置)，保守判待确认而非误报
        return _banded_unknown(banded, f"{label}：分档未覆盖当前取值，待确认")

    actual = _actual_value(profile, banded.metric, today)
    band_hint = band.label or f"门槛 {_fmt(band.threshold)}"
    if actual is None:
        return _banded_unknown(banded, f"{label}：已落入「{band_hint}」档，但档案未填该指标，待确认",
                               threshold=band.threshold)

    if banded.op is ConditionOperator.GTE:
        met = actual >= band.threshold
    else:
        met = actual <= band.threshold
    sign = "≥" if banded.op is ConditionOperator.GTE else "≤"
    verdict = "达标" if met else "不达标"
    detail = (f"{label}：落入「{band_hint}」档，实际 {_fmt(actual)}，"
              f"要求 {sign} {_fmt(band.threshold)}（{verdict}）")
    return ConditionCheck(
        metric=banded.metric, op=banded.op, threshold=band.threshold, label=banded.label,
        actual=actual, status=ConditionStatus.MET if met else ConditionStatus.UNMET, detail=detail,
    )


def _banded_unknown(
    banded: BandedCondition, detail: str, threshold: float = 0.0,
) -> ConditionCheck:
    """分档条件无法核验时的"待确认"结果(threshold 仅占位，未真正参与比较)。"""
    return ConditionCheck(
        metric=banded.metric, op=banded.op, threshold=threshold, label=banded.label,
        actual=None, status=ConditionStatus.UNKNOWN, detail=detail,
    )


def _missing_prerequisites(profile: EnterpriseProfile, qual: Qualification) -> List[str]:
    """前置资质缺口(与能力① 同口径：子串双向包含视为已持有)。"""
    return [
        p for p in qual.prerequisites
        if not any(p in q or q in p for q in profile.qualifications)
    ]


def analyze_gap(
    profile: EnterpriseProfile,
    qual: Qualification,
    today: Optional[date] = None,
) -> QualificationGapReport:
    """对单条资质做结构化差距分析，产出逐条核验 + 待人工确认条件 + 前置缺口。

    核验项 = 平铺硬条件(structured_conditions) + 分档硬条件(banded_conditions)；两类的
    label 均从 manual_review 去重(避免与 key_conditions 文案重复展示)。
    """
    checks = [_evaluate(profile, c, today) for c in qual.structured_conditions]
    checks += [_evaluate_banded(profile, b, today) for b in qual.banded_conditions]

    structured_labels = {c.label for c in qual.structured_conditions if c.label}
    structured_labels |= {b.label for b in qual.banded_conditions if b.label}
    manual_review = [c for c in qual.key_conditions if c not in structured_labels]

    met = sum(1 for c in checks if c.status is ConditionStatus.MET)
    unmet = sum(1 for c in checks if c.status is ConditionStatus.UNMET)
    unknown = sum(1 for c in checks if c.status is ConditionStatus.UNKNOWN)
    prereq_missing = _missing_prerequisites(profile, qual)

    return QualificationGapReport(
        qualification=qual,
        checks=checks,
        manual_review=manual_review,
        prerequisites_missing=prereq_missing,
        met_count=met,
        unmet_count=unmet,
        unknown_count=unknown,
        summary=_build_summary(met, unmet, unknown, len(manual_review), prereq_missing),
    )


def _build_summary(
    met: int, unmet: int, unknown: int, manual: int, prereq_missing: List[str],
) -> str:
    """一句话总览，引导用户优先补齐"待确认"与"不达标"。"""
    structured_total = met + unmet + unknown
    parts: List[str] = []
    if structured_total:
        parts.append(f"可核验 {structured_total} 项：达标 {met}、不达标 {unmet}、待确认 {unknown}")
    if prereq_missing:
        parts.append(f"缺前置资质 {len(prereq_missing)} 项")
    if manual:
        parts.append(f"另有 {manual} 项需结合材料人工确认")
    return "；".join(parts) if parts else "暂无可结构化核验的条件，详见核心条件与材料清单"
