from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.domain.models.contest import ContestSource, ContestSubscription
from app.domain.models.policy import Policy


class ContestItemResponse(BaseModel):
    id: str
    title: str
    source: str
    source_name: str
    origin: str
    source_url: str
    region: str
    publish_date: Optional[date] = None
    apply_deadline: Optional[date] = None
    deadline_status: str = "unknown"

    @classmethod
    def from_domain(cls, value: Policy) -> "ContestItemResponse":
        return cls(id=value.id, title=value.title, source=value.source,
                   source_name=value.source_name or value.source, origin=value.origin_type,
                   source_url=value.source_url, region=value.region, publish_date=value.publish_date,
                   apply_deadline=value.apply_deadline, deadline_status=value.deadline_status)


class ContestDetailResponse(ContestItemResponse):
    body_text: str = ""
    apply_window_text: str = ""

    @classmethod
    def from_domain(cls, value: Policy) -> "ContestDetailResponse":
        return cls(**ContestItemResponse.from_domain(value).model_dump(), body_text=value.body_text,
                   apply_window_text=value.apply_window_text)


class ContestListResponse(BaseModel):
    items: List[ContestItemResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ContestSourceRequest(BaseModel):
    key: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    region: str = Field(default="全国", max_length=128)
    home_url: str = Field(min_length=8, max_length=1024)
    adapter_type: str = Field(min_length=2, max_length=64)
    adapter_config: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class ContestSourcePatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    region: Optional[str] = Field(default=None, max_length=128)
    home_url: Optional[str] = Field(default=None, min_length=8, max_length=1024)
    adapter_type: Optional[str] = Field(default=None, min_length=2, max_length=64)
    adapter_config: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None


class ContestSourceResponse(BaseModel):
    id: str
    key: str
    name: str
    region: str
    home_url: str
    adapter_type: str
    adapter_config: Dict[str, str] = Field(default_factory=dict)
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, value: ContestSource) -> "ContestSourceResponse":
        return cls(**value.model_dump())


class ContestSourceListResponse(BaseModel):
    items: List[ContestSourceResponse] = Field(default_factory=list)


class ContestSubscriptionRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=128)


class ContestSubscriptionPatchRequest(BaseModel):
    enabled: bool


class ContestSubscriptionResponse(BaseModel):
    id: str
    keyword: str
    enabled: bool
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, value: ContestSubscription) -> "ContestSubscriptionResponse":
        return cls(id=value.id, keyword=value.keyword, enabled=value.enabled,
                   last_run_at=value.last_run_at, created_at=value.created_at, updated_at=value.updated_at)


class ContestSubscriptionListResponse(BaseModel):
    items: List[ContestSubscriptionResponse] = Field(default_factory=list)
