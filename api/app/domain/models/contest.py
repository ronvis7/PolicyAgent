import uuid
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ContestSource(BaseModel):
    """平台维护的可信官方赛事来源。"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str
    name: str
    region: str = "全国"
    home_url: str
    adapter_type: str
    adapter_config: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ContestSubscription(BaseModel):
    """租户自己的全网赛事发现关键词。"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    keyword: str
    enabled: bool = True
    last_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ContestDiscoveryHit(BaseModel):
    """A tenant-private record that prevents repeat discovery notifications."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    subscription_id: str
    policy_id: str
    created_at: datetime = Field(default_factory=datetime.now)


class TenantContestSource(BaseModel):
    """A static HTML contest portal owned by exactly one tenant."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    name: str
    region: str
    list_url: str
    title_keywords: str = ""
    link_selector: str
    content_selector: str
    preset_source_id: Optional[str] = None
    enabled: bool = False
    preflight_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ContestRun(BaseModel):
    """Tenant-scoped audit record for either a source crawl or web discovery."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    kind: str  # source / discovery
    target_id: str
    status: str = "running"  # running / succeeded / failed
    trigger: str = "manual"  # manual / scheduled
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    searched_count: int = 0
    valid_count: int = 0
    stored_count: int = 0
    feed_new_count: int = 0
    error_message: str = ""
