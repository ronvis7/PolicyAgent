import uuid
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.models.policy_match import PolicyMatch
from app.domain.models.qualification import QualificationMatch


class FeedStatus(str, Enum):
    """工作台 Feed 条目状态机(④)"""
    UNREAD = "unread"    # 新增未读(驱动左栏红点；"自上次以来新增"天然等价 unread)
    READ = "read"        # 已读
    APPLIED = "applied"  # 已申报
    IGNORED = "ignored"  # 已忽略


class FeedItemType(str, Enum):
    """机会类型。④ 当前仅政策；资质/比赛(⑥)为扩展位，避免后续改表。"""
    POLICY = "policy"
    QUALIFICATION = "qualification"
    COMPETITION = "competition"


class FeedItem(BaseModel):
    """工作台 Feed 的持久化机会条目(④：把③即时匹配结果物化)。

    一租户一机会((tenant_id, policy_id) 唯一)。计算快照(标题/分数/理由)随重算更新，
    但 status 与 created_at 由用户行为驱动、重算时保留(见 FeedService.recompute_for_tenant)，
    避免已申报/已忽略被刷掉。快照直接落表使 Feed 列表单表查询免 N+1，机会源变动也稳定。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""  # 所属租户
    type: FeedItemType = FeedItemType.POLICY  # 机会类型(⑥ 扩展位)
    policy_id: str = ""  # 关联机会源id(当前=政策id)
    # ---- 计算快照(展示用) ----
    title: str = ""
    issuer: str = ""
    publish_date: Optional[date] = None
    source_url: str = ""
    region: str = ""
    score: float = 0.0  # RRF 融合总分
    structured_score: float = 0.0  # 结构化命中归一化分∈[0,1]
    semantic_score: float = 0.0  # 语义最高相似度
    matched_terms: List[str] = Field(default_factory=list)  # 命中的档案词
    reasons: List[str] = Field(default_factory=list)  # 可读推荐理由
    # ---- 申报截止快照(主线⑤；资质无截止概念，留默认) ----
    apply_deadline: Optional[date] = None  # 申报截止日期(仅 deadline_status=extracted 时有值)
    deadline_status: str = "unknown"  # extracted / rolling / unknown
    # ---- 状态机 ----
    status: FeedStatus = FeedStatus.UNREAD
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_policy_match(cls, tenant_id: str, match: PolicyMatch) -> "FeedItem":
        """由③政策匹配候选构造一条 Feed 条目(新条目，status 默认 unread)。"""
        p = match.policy
        return cls(
            tenant_id=tenant_id,
            type=FeedItemType.POLICY,
            policy_id=p.id,
            title=p.title,
            issuer=p.issuer,
            publish_date=p.publish_date,
            source_url=p.source_url,
            region=p.region,
            score=match.score,
            structured_score=match.structured_score,
            semantic_score=match.semantic_score,
            matched_terms=match.matched_terms,
            reasons=match.reasons,
            apply_deadline=p.apply_deadline,
            deadline_status=p.deadline_status,
        )

    @classmethod
    def from_qualification_match(
        cls, tenant_id: str, match: QualificationMatch,
    ) -> "FeedItem":
        """由⑥资质匹配候选构造一条 Feed 条目(type=qualification，新条目默认 unread)。

        资质无发布日期/抓取来源，故 publish_date/source_url 留空；policy_id 复用为资质 key
        (机会源id)，与政策 UUID 不冲突。structured_score 承载匹配总分，便于与政策同列排序。
        """
        q = match.qualification
        return cls(
            tenant_id=tenant_id,
            type=FeedItemType.QUALIFICATION,
            policy_id=q.key,
            title=q.name,
            issuer=q.issuer,
            region=q.region,
            score=match.score,
            structured_score=match.score,
            matched_terms=match.matched_signals,
            reasons=match.reasons,
        )

    def with_snapshot_from(self, other: "FeedItem") -> "FeedItem":
        """用 other 的计算快照更新本条目，保留 id/status/created_at(重算不覆盖用户状态)。"""
        return self.model_copy(update={
            "title": other.title,
            "issuer": other.issuer,
            "publish_date": other.publish_date,
            "source_url": other.source_url,
            "region": other.region,
            "score": other.score,
            "structured_score": other.structured_score,
            "semantic_score": other.semantic_score,
            "matched_terms": other.matched_terms,
            "reasons": other.reasons,
            "apply_deadline": other.apply_deadline,
            "deadline_status": other.deadline_status,
            "updated_at": datetime.now(),
        })
