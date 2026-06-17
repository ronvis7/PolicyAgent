from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.models.policy import Policy
from app.domain.models.policy_match import PolicyMatch


class PolicyListItem(BaseModel):
    """政策列表项(不含正文，保持列表轻量)"""
    id: str = ""
    source: str = ""
    source_url: str = ""
    index_number: str = ""
    title: str = ""
    issuer: str = ""
    doc_number: str = ""
    status: str = ""
    publish_date: Optional[date] = None
    region: str = ""

    @classmethod
    def from_domain(cls, p: Policy) -> "PolicyListItem":
        return cls(
            id=p.id, source=p.source, source_url=p.source_url,
            index_number=p.index_number, title=p.title, issuer=p.issuer,
            doc_number=p.doc_number, status=p.status,
            publish_date=p.publish_date, region=p.region,
        )


class PolicyListResponse(BaseModel):
    """政策分页列表响应"""
    items: List[PolicyListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class PolicyDetailResponse(PolicyListItem):
    """政策详情响应(含正文、时间戳与申报截止)"""
    body_text: str = ""
    crawled_at: Optional[datetime] = None
    # ---- 申报截止(主线⑤；LLM 抽取，以原文为准、供参考核对) ----
    apply_deadline: Optional[date] = None
    apply_window_text: str = ""
    deadline_status: str = "unknown"  # extracted / rolling / unknown

    @classmethod
    def from_domain(cls, p: Policy) -> "PolicyDetailResponse":
        return cls(
            id=p.id, source=p.source, source_url=p.source_url,
            index_number=p.index_number, title=p.title, issuer=p.issuer,
            doc_number=p.doc_number, status=p.status,
            publish_date=p.publish_date, region=p.region,
            body_text=p.body_text, crawled_at=p.crawled_at,
            apply_deadline=p.apply_deadline, apply_window_text=p.apply_window_text,
            deadline_status=p.deadline_status,
        )


class PolicyMatchItem(BaseModel):
    """单条政策匹配候选(③匹配输出)：政策概要 + 融合分 + 可解释理由"""
    policy: PolicyListItem  # 政策概要(列表轻量，正文经详情接口按需取)
    score: float = 0.0  # RRF 融合总分(越大越靠前)
    structured_score: float = 0.0  # 结构化命中归一化分∈[0,1]
    semantic_score: float = 0.0  # 语义最高相似度∈[-1,1]
    matched_terms: List[str] = Field(default_factory=list)  # 命中的档案词
    reasons: List[str] = Field(default_factory=list)  # 推荐理由

    @classmethod
    def from_domain(cls, m: PolicyMatch) -> "PolicyMatchItem":
        return cls(
            policy=PolicyListItem.from_domain(m.policy),
            score=m.score, structured_score=m.structured_score,
            semantic_score=m.semantic_score, matched_terms=m.matched_terms,
            reasons=m.reasons,
        )


class PolicyMatchResponse(BaseModel):
    """政策匹配响应：候选列表(已按融合分倒序)"""
    items: List[PolicyMatchItem] = Field(default_factory=list)
    total: int = 0


class PolicySourceItem(BaseModel):
    """一个公开政策来源(地区/门户)"""
    key: str = ""  # 稳定标识(抓取时传入)
    name: str = ""  # 展示名
    region: str = ""  # 适用地区


class PolicySourceListResponse(BaseModel):
    """可抓取的政策来源列表"""
    items: List[PolicySourceItem] = Field(default_factory=list)
