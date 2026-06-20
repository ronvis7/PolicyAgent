"""主动情报简报接口 schema。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.domain.models.intel_briefing import IntelBriefing


class BriefingItemSchema(BaseModel):
    """一条情报要点的对外表示。"""
    title: str
    category: str
    reason: str
    action: str
    urgency: str


class BriefingResponse(BaseModel):
    """情报简报响应（latest 为 None 时返回 has_briefing=false）。"""
    has_briefing: bool
    headline: str = ""
    items: List[BriefingItemSchema] = []
    generated_by: str = ""
    disclaimer: str = ""
    generated_at: Optional[datetime] = None

    @classmethod
    def from_domain(cls, briefing: Optional[IntelBriefing]) -> "BriefingResponse":
        if briefing is None:
            return cls(has_briefing=False)
        return cls(
            has_briefing=True,
            headline=briefing.headline,
            items=[
                BriefingItemSchema(
                    title=i.title, category=i.category, reason=i.reason,
                    action=i.action, urgency=i.urgency.value,
                )
                for i in briefing.items
            ],
            generated_by=briefing.generated_by,
            disclaimer=briefing.disclaimer,
            generated_at=briefing.generated_at,
        )
