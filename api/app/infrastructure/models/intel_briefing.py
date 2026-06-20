from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.intel_briefing import BriefingItem, IntelBriefing


class IntelBriefingModel(Base):
    """主动情报简报 ORM（每租户最新一份，覆盖式保存）。

    简报正文（headline/items/生成方式/免责）整体存入 content(JSONB)，便于增量演进字段；
    generated_at 单列承载，供排序/展示"上次生成时间"。tenant_id 主键兼外键(ON DELETE CASCADE)。
    """
    __tablename__ = "intel_briefings"

    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    content: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )  # {headline, items[], generated_by, disclaimer}
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"),
    )

    @classmethod
    def _content_from_domain(cls, briefing: IntelBriefing) -> dict:
        return {
            "headline": briefing.headline,
            "items": [item.model_dump(mode="json") for item in briefing.items],
            "generated_by": briefing.generated_by,
            "disclaimer": briefing.disclaimer,
        }

    @classmethod
    def from_domain(cls, briefing: IntelBriefing) -> "IntelBriefingModel":
        return cls(
            tenant_id=briefing.tenant_id,
            content=cls._content_from_domain(briefing),
            generated_at=briefing.generated_at,
        )

    def to_domain(self) -> IntelBriefing:
        content = self.content or {}
        items = [BriefingItem.model_validate(raw) for raw in content.get("items", [])]
        return IntelBriefing(
            tenant_id=self.tenant_id,
            headline=content.get("headline", ""),
            items=items,
            generated_by=content.get("generated_by", "fallback"),
            disclaimer=content.get("disclaimer", IntelBriefing.model_fields["disclaimer"].default),
            generated_at=self.generated_at,
        )

    def update_from_domain(self, briefing: IntelBriefing) -> None:
        self.content = self._content_from_domain(briefing)
        self.generated_at = briefing.generated_at
