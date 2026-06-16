"""企业档案 × 资质目录的纯函数匹配逻辑（主线⑥ 能力①的可测内核，无 IO）。

与 ③ 政策匹配不同：资质目录有限且结构化，故走**确定性的启发式匹配**而非向量召回：
1. 地区门槛：国家级/通用体系认证恒适用；省级按档案省份；市/区级按档案市/区。地区不适用直接排除。
2. 信号重合：资质 `match_signals` 落在档案画像文本(关键词/技术域/已有资质/行业/主营)中即命中。
3. 前置资质：资质 `prerequisites` 需在档案 `qualifications` 中已持有，缺失计入差距。

判定"可申报(eligible)"= 无前置缺失 且 信号覆盖率达阈值；否则"接近可申报(差N项)"。
结果仅为启发式提示，最终以官方办法为准(见 Qualification.disclaimer)。
"""

from typing import List, Optional

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import (
    Qualification,
    QualificationLevel,
    QualificationMatch,
)

# 信号覆盖率达到该比例(且无前置缺失)即判定"可申报"
ELIGIBLE_SIGNAL_COVERAGE = 0.6


def build_profile_text(profile: EnterpriseProfile) -> str:
    """拼接档案画像为一段文本，供资质信号做子串命中(关键词/技术域/已有资质/行业/主营)。"""
    parts: List[str] = []
    parts.extend(profile.keywords)
    parts.extend(profile.tech_domains)
    parts.extend(profile.qualifications)
    parts.append(profile.industry)
    parts.append(profile.main_business)
    return " ".join(p.strip() for p in parts if p and p.strip())


def region_applies(profile: EnterpriseProfile, qual: Qualification) -> bool:
    """资质适用地区是否覆盖档案所在地。

    国家级/通用恒适用；省级要求档案省份与资质地区相含；市/区级要求市或区相含。
    """
    if qual.level in (QualificationLevel.NATIONAL, QualificationLevel.GENERAL):
        return True

    region = (qual.region or "").strip()
    if not region:
        return False

    if qual.level == QualificationLevel.PROVINCIAL:
        province = (profile.province or "").strip()
        return bool(province) and (province in region or region in province)

    # MUNICIPAL：市或区任一相含即可(覆盖"无锡市"与"无锡市新吴区"两种写法)
    for level in (profile.district, profile.city):
        level = (level or "").strip()
        if level and (level in region or region in level):
            return True
    return False


def match_qualification(
    profile: EnterpriseProfile, qual: Qualification,
) -> Optional[QualificationMatch]:
    """对单条资质做启发式匹配；地区不适用返回 None(应从结果中排除)。"""
    if not region_applies(profile, qual):
        return None

    text = build_profile_text(profile)
    matched_signals = [s for s in qual.match_signals if s and s in text]
    missing_signals = [s for s in qual.match_signals if s and s not in text]

    held_prereqs = [
        p for p in qual.prerequisites
        if any(p in q or q in p for q in profile.qualifications)
    ]
    missing_prerequisites = [p for p in qual.prerequisites if p not in held_prereqs]

    total = len(qual.match_signals) + len(qual.prerequisites)
    got = len(matched_signals) + len(held_prereqs)
    score = got / total if total else 0.0

    coverage = (
        len(matched_signals) / len(qual.match_signals) if qual.match_signals else 1.0
    )
    eligible = (not missing_prerequisites) and coverage >= ELIGIBLE_SIGNAL_COVERAGE

    return QualificationMatch(
        qualification=qual,
        score=score,
        matched_signals=matched_signals,
        missing_signals=missing_signals,
        missing_prerequisites=missing_prerequisites,
        eligible=eligible,
        reasons=_build_reasons(matched_signals, missing_signals, missing_prerequisites, eligible),
    )


def match_qualifications(
    profile: EnterpriseProfile, catalog: List[Qualification],
) -> List[QualificationMatch]:
    """对整份目录匹配，排除地区不适用项，按(可申报优先, 分数倒序)排序。"""
    results: List[QualificationMatch] = []
    for qual in catalog:
        match = match_qualification(profile, qual)
        if match is not None:
            results.append(match)
    results.sort(key=lambda m: (m.eligible, m.score), reverse=True)
    return results


def _build_reasons(
    matched_signals: List[str],
    missing_signals: List[str],
    missing_prerequisites: List[str],
    eligible: bool,
) -> List[str]:
    """构建可读理由：可申报/接近 + 命中信号 + 待补信号 + 前置缺失。"""
    reasons: List[str] = []
    gap = len(missing_signals) + len(missing_prerequisites)
    reasons.append("可申报" if eligible else f"接近可申报（差 {gap} 项）")
    if matched_signals:
        reasons.append(f"符合：{'、'.join(matched_signals)}")
    if missing_prerequisites:
        reasons.append(f"前置资质缺失：{'、'.join(missing_prerequisites)}")
    if missing_signals:
        reasons.append(f"尚需具备：{'、'.join(missing_signals)}")
    return reasons
