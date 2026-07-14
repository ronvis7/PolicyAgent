import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.contest import ContestDiscoveryHit, ContestSource, ContestSubscription
from .base import Base


class ContestSourceModel(Base):
    __tablename__ = "contest_sources"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False, server_default=text("'全国'"))
    home_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, onupdate=datetime.now, server_default=text("CURRENT_TIMESTAMP(0)"))

    def to_domain(self) -> ContestSource:
        return ContestSource(id=self.id, key=self.key, name=self.name, region=self.region,
                             home_url=self.home_url, adapter_type=self.adapter_type,
                             adapter_config=self.adapter_config or {}, enabled=self.enabled,
                             created_at=self.created_at, updated_at=self.updated_at)

    @classmethod
    def from_domain(cls, value: ContestSource) -> "ContestSourceModel":
        return cls(**value.model_dump())

    def update_from_domain(self, value: ContestSource) -> None:
        self.key, self.name, self.region = value.key, value.name, value.region
        self.home_url, self.adapter_type = value.home_url, value.adapter_type
        self.adapter_config, self.enabled = value.adapter_config, value.enabled


class ContestSubscriptionModel(Base):
    __tablename__ = "contest_subscriptions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, onupdate=datetime.now, server_default=text("CURRENT_TIMESTAMP(0)"))

    def to_domain(self) -> ContestSubscription:
        return ContestSubscription(id=self.id, tenant_id=self.tenant_id, keyword=self.keyword,
                                   enabled=self.enabled, last_run_at=self.last_run_at,
                                   created_at=self.created_at, updated_at=self.updated_at)

    @classmethod
    def from_domain(cls, value: ContestSubscription) -> "ContestSubscriptionModel":
        return cls(**value.model_dump())

    def update_from_domain(self, value: ContestSubscription) -> None:
        self.keyword, self.enabled, self.last_run_at = value.keyword, value.enabled, value.last_run_at


class ContestDiscoveryHitModel(Base):
    __tablename__ = "contest_discovery_hits"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(255), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(String(255), ForeignKey("contest_subscriptions.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(255), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @classmethod
    def from_domain(cls, value: ContestDiscoveryHit) -> "ContestDiscoveryHitModel":
        return cls(**value.model_dump())
