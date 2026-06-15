"""资质申报机会接口 schema（主线⑥）。

`QualificationMatchResponse` 服务"可申报资质"列表(档案匹配视图)；`QualificationDetailResponse`
服务详情页，**强制携带 disclaimer + last_reviewed**(风险纪律：数值类条件以官方办法为准)。
"""

from typing import List

from pydantic import BaseModel, Field

from app.domain.models.qualification import Qualification, QualificationMatch


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
