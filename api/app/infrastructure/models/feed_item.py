import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.feed_item import FeedItem, FeedItemType, FeedStatus


class FeedItemModel(Base):
    """工作台 Feed 条目 ORM（④：物化的政策/机会信息流，按租户隔离）。

    (tenant_id, policy_id) 唯一——一租户一机会一条，重算走 upsert。计算快照直接落列，
    list 单表查询免 N+1；status 用 String 存枚举值(与 membership 等一致，不用 sa.Enum)。
    """
    __tablename__ = "policy_matches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_id", name="uq_policy_matches_tenant_policy"),
    )

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'policy'"),
    )  # 机会类型(policy/qualification/competition，⑥ 扩展位)
    policy_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # ---- 计算快照 ----
    title: Mapped[str] = mapped_column(String(512), nullable=False, server_default=text("''"))
    issuer: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    publish_date: Mapped[date] = mapped_column(Date, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False, server_default=text("''"))
    region: Mapped[str] = mapped_column(String(128), nullable=False, server_default=text("''"))
    score: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    structured_score: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    matched_terms: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"),
    )
    reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"),
    )
    # ---- 状态机 ----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'unread'"), index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"),
    )

    @classmethod
    def from_domain(cls, item: FeedItem) -> "FeedItemModel":
        return cls(
            id=item.id,
            tenant_id=item.tenant_id,
            type=item.type.value,
            policy_id=item.policy_id,
            title=item.title,
            issuer=item.issuer,
            publish_date=item.publish_date,
            source_url=item.source_url,
            region=item.region,
            score=item.score,
            structured_score=item.structured_score,
            semantic_score=item.semantic_score,
            matched_terms=list(item.matched_terms),
            reasons=list(item.reasons),
            status=item.status.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def to_domain(self) -> FeedItem:
        return FeedItem(
            id=self.id,
            tenant_id=self.tenant_id,
            type=FeedItemType(self.type),
            policy_id=self.policy_id,
            title=self.title,
            issuer=self.issuer,
            publish_date=self.publish_date,
            source_url=self.source_url,
            region=self.region,
            score=self.score,
            structured_score=self.structured_score,
            semantic_score=self.semantic_score,
            matched_terms=list(self.matched_terms or []),
            reasons=list(self.reasons or []),
            status=FeedStatus(self.status),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def update_from_domain(self, item: FeedItem) -> None:
        """整体更新业务字段(保留 id；自然键 tenant_id/policy_id 不变)。"""
        self.type = item.type.value
        self.title = item.title
        self.issuer = item.issuer
        self.publish_date = item.publish_date
        self.source_url = item.source_url
        self.region = item.region
        self.score = item.score
        self.structured_score = item.structured_score
        self.semantic_score = item.semantic_score
        self.matched_terms = list(item.matched_terms)
        self.reasons = list(item.reasons)
        self.status = item.status.value
        self.created_at = item.created_at
        self.updated_at = item.updated_at
