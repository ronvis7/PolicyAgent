from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.app_config import EmbedConfig, LLMConfig
from ...domain.models.tenant_settings import ContestSearchConfig, FeishuNotifyConfig, TenantSettings


class TenantSettingsModel(Base):
    """租户级设置ORM模型，每个租户一行，承载LLM与Embedding配置覆盖"""
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )  # 租户id(主键兼外键)
    # 三列均 none_as_null=True：显式赋 None 落 SQL NULL 而非 JSONB 'null'
    # ('null'::jsonb IS NOT NULL 为真，会让 feishu_config 的 IS NOT NULL 过滤误匹配所有行)
    llm_config: Mapped[Optional[dict]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )  # 组织自定义LLM配置(JSON)，NULL表示未覆盖
    embed_config: Mapped[Optional[dict]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )  # 组织自定义Embedding配置(JSON，仅api_key生效)，NULL表示未覆盖
    feishu_config: Mapped[Optional[dict]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )  # 组织飞书群webhook配置(JSON，新赛事即推)，NULL表示未开启
    contest_search_config: Mapped[Optional[dict]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )  # 组织赛事搜索凭据(JSON)，NULL表示回落平台配置
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 更新时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 创建时间

    @classmethod
    def from_domain(cls, settings: TenantSettings) -> "TenantSettingsModel":
        """从领域模型创建ORM模型"""
        return cls(
            tenant_id=settings.tenant_id,
            llm_config=settings.llm_config.model_dump(mode="json") if settings.llm_config else None,
            embed_config=settings.embed_config.model_dump(mode="json") if settings.embed_config else None,
            feishu_config=settings.feishu_config.model_dump(mode="json") if settings.feishu_config else None,
            contest_search_config=(
                settings.contest_search_config.model_dump(mode="json")
                if settings.contest_search_config else None
            ),
            updated_at=settings.updated_at,
            created_at=settings.created_at,
        )

    def to_domain(self) -> TenantSettings:
        """将ORM模型转换为领域模型"""
        return TenantSettings(
            tenant_id=self.tenant_id,
            llm_config=LLMConfig.model_validate(self.llm_config) if self.llm_config else None,
            embed_config=EmbedConfig.model_validate(self.embed_config) if self.embed_config else None,
            feishu_config=FeishuNotifyConfig.model_validate(self.feishu_config) if self.feishu_config else None,
            contest_search_config=(
                ContestSearchConfig.model_validate(self.contest_search_config)
                if self.contest_search_config else None
            ),
            updated_at=self.updated_at,
            created_at=self.created_at,
        )

    def update_from_domain(self, settings: TenantSettings) -> None:
        """从领域模型更新数据"""
        self.llm_config = settings.llm_config.model_dump(mode="json") if settings.llm_config else None
        self.embed_config = settings.embed_config.model_dump(mode="json") if settings.embed_config else None
        self.feishu_config = settings.feishu_config.model_dump(mode="json") if settings.feishu_config else None
        self.contest_search_config = (
            settings.contest_search_config.model_dump(mode="json")
            if settings.contest_search_config else None
        )
