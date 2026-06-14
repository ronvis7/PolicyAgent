from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.models.policy import Policy


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
    """政策详情响应(含正文与时间戳)"""
    body_text: str = ""
    crawled_at: Optional[datetime] = None

    @classmethod
    def from_domain(cls, p: Policy) -> "PolicyDetailResponse":
        return cls(
            id=p.id, source=p.source, source_url=p.source_url,
            index_number=p.index_number, title=p.title, issuer=p.issuer,
            doc_number=p.doc_number, status=p.status,
            publish_date=p.publish_date, region=p.region,
            body_text=p.body_text, crawled_at=p.crawled_at,
        )
