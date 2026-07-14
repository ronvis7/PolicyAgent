import uuid
from datetime import datetime
from typing import Dict

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
