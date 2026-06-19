"""资质申报机会接口 schema（主线⑥）。

`QualificationMatchResponse` 服务"可申报资质"列表(档案匹配视图)；`QualificationDetailResponse`
服务详情页，**强制携带 disclaimer + last_reviewed**(风险纪律：数值类条件以官方办法为准)。
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.models.qualification import (
    Qualification,
    QualificationGapReport,
    QualificationMatch,
)


class QualificationDetailResponse(BaseModel):
    """资质详情(展示用，含风险纪律字段)"""
    key: str = ""
    name: str = ""
    level: str = ""
    issuer: str = ""
    category: str = ""
    region: str = ""
    key_conditions: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    timing: str = ""
    policy_basis: str = ""
    benefit: str = ""
    last_reviewed: str = ""
    disclaimer: str = ""

    @classmethod
    def from_domain(cls, q: Qualification) -> "QualificationDetailResponse":
        return cls(
            key=q.key, name=q.name, level=q.level.value, issuer=q.issuer,
            category=q.category, region=q.region, key_conditions=q.key_conditions,
            materials=q.materials, timing=q.timing, policy_basis=q.policy_basis,
            benefit=q.benefit, last_reviewed=q.last_reviewed, disclaimer=q.disclaimer,
        )


class QualificationSourceItem(BaseModel):
    """资质目录来源条目(全量、非租户过滤)，供「数据来源」页溯源展示。

    资质目录为结构化整理、非实时爬取，强制携带 last_reviewed + disclaimer(风险纪律)。
    """
    key: str = ""
    name: str = ""
    level: str = ""
    issuer: str = ""  # 发证/认定机关
    region: str = ""
    policy_basis: str = ""  # 政策依据(办法/文号)
    last_reviewed: str = ""
    disclaimer: str = ""

    @classmethod
    def from_domain(cls, q: Qualification) -> "QualificationSourceItem":
        return cls(
            key=q.key, name=q.name, level=q.level.value, issuer=q.issuer,
            region=q.region, policy_basis=q.policy_basis,
            last_reviewed=q.last_reviewed, disclaimer=q.disclaimer,
        )


class QualificationCatalogResponse(BaseModel):
    """全量资质目录来源列表(数据来源页用)"""
    items: List[QualificationSourceItem] = Field(default_factory=list)
    total: int = 0


class QualificationMatchResponse(BaseModel):
    """单条资质匹配结果(可申报/接近 + 差距雏形)"""
    key: str = ""
    name: str = ""
    level: str = ""
    issuer: str = ""
    category: str = ""
    region: str = ""
    score: float = 0.0
    eligible: bool = False
    matched_signals: List[str] = Field(default_factory=list)
    missing_signals: List[str] = Field(default_factory=list)
    missing_prerequisites: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, match: QualificationMatch) -> "QualificationMatchResponse":
        q = match.qualification
        return cls(
            key=q.key, name=q.name, level=q.level.value, issuer=q.issuer,
            category=q.category, region=q.region, score=match.score,
            eligible=match.eligible, matched_signals=match.matched_signals,
            missing_signals=match.missing_signals,
            missing_prerequisites=match.missing_prerequisites, reasons=match.reasons,
        )


class QualificationMatchListResponse(BaseModel):
    """可申报资质列表响应"""
    items: List[QualificationMatchResponse] = Field(default_factory=list)
    total: int = 0
    eligible_count: int = 0  # 其中"可申报"条数(给前端做角标/概览)


class ConditionCheckResponse(BaseModel):
    """单条硬条件核验结果(达标/不达标/待确认)"""
    metric: str = ""
    op: str = ""
    threshold: float = 0.0
    label: str = ""
    actual: Optional[float] = None
    status: str = ""  # met/unmet/unknown
    detail: str = ""


class QualificationGapResponse(BaseModel):
    """资质条件差距分析响应(能力②)，强制携带 disclaimer + last_reviewed。"""
    key: str = ""
    name: str = ""
    checks: List[ConditionCheckResponse] = Field(default_factory=list)
    manual_review: List[str] = Field(default_factory=list)
    prerequisites_missing: List[str] = Field(default_factory=list)
    met_count: int = 0
    unmet_count: int = 0
    unknown_count: int = 0
    summary: str = ""
    last_reviewed: str = ""
    disclaimer: str = ""

    @classmethod
    def from_domain(cls, report: QualificationGapReport) -> "QualificationGapResponse":
        q = report.qualification
        return cls(
            key=q.key,
            name=q.name,
            checks=[
                ConditionCheckResponse(
                    metric=c.metric.value, op=c.op.value, threshold=c.threshold,
                    label=c.label, actual=c.actual, status=c.status.value, detail=c.detail,
                )
                for c in report.checks
            ],
            manual_review=report.manual_review,
            prerequisites_missing=report.prerequisites_missing,
            met_count=report.met_count,
            unmet_count=report.unmet_count,
            unknown_count=report.unknown_count,
            summary=report.summary,
            last_reviewed=q.last_reviewed,
            disclaimer=q.disclaimer,
        )
