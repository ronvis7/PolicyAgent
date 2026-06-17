from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.models.feed_item import FeedItem, FeedStatus


# 用户可手动设置的状态(不含 unread——unread 由重算新增驱动，不应手动回设)
_SETTABLE_STATUSES = {FeedStatus.READ.value, FeedStatus.APPLIED.value, FeedStatus.IGNORED.value}


class FeedItemResponse(BaseModel):
    """工作台 Feed 条目响应(计算快照 + 状态)"""
    id: str = ""
    type: str = "policy"
    policy_id: str = ""
    title: str = ""
    issuer: str = ""
    publish_date: Optional[date] = None
    source_url: str = ""
    region: str = ""
    score: float = 0.0
    structured_score: float = 0.0
    semantic_score: float = 0.0
    matched_terms: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    # ---- 申报截止(主线⑤) ----
    apply_deadline: Optional[date] = None
    deadline_status: str = "unknown"  # extracted / rolling / unknown
    days_left: Optional[int] = None  # 距截止剩余天数(仅 extracted 时算；可为负=已过期)
    status: str = "unread"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_domain(cls, item: FeedItem) -> "FeedItemResponse":
        days_left = (
            (item.apply_deadline - date.today()).days
            if item.apply_deadline is not None
            else None
        )
        return cls(
            id=item.id, type=item.type.value, policy_id=item.policy_id,
            title=item.title, issuer=item.issuer, publish_date=item.publish_date,
            source_url=item.source_url, region=item.region, score=item.score,
            structured_score=item.structured_score, semantic_score=item.semantic_score,
            matched_terms=item.matched_terms, reasons=item.reasons,
            apply_deadline=item.apply_deadline, deadline_status=item.deadline_status,
            days_left=days_left,
            status=item.status.value, created_at=item.created_at, updated_at=item.updated_at,
        )


class FeedListResponse(BaseModel):
    """工作台 Feed 分页列表响应"""
    items: List[FeedItemResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class UnreadCountResponse(BaseModel):
    """未读计数响应(左栏红点)"""
    count: int = 0


class ExpiringListResponse(BaseModel):
    """临期申报机会响应(主线⑤：未来 N 天内截止，最紧的在前)"""
    items: List[FeedItemResponse] = Field(default_factory=list)
    count: int = 0
    within_days: int = 14


class RecomputeResponse(BaseModel):
    """重算结果响应"""
    new: int = 0
    updated: int = 0


class SetFeedStatusRequest(BaseModel):
    """更新 Feed 条目状态请求(read/applied/ignored)"""
    status: str

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in _SETTABLE_STATUSES:
            raise ValueError(f"status 必须是 {sorted(_SETTABLE_STATUSES)} 之一")
        return v
