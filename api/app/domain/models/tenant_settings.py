from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.models.app_config import EmbedConfig, LLMConfig


class TenantSettings(BaseModel):
    """租户级设置领域模型，承载组织对平台默认配置的覆盖。

    承载 LLM 与 Embedding 配置覆盖(BYO key)：对应字段为 None 表示该组织未自定义，
    运行时回落到平台默认配置(LLM→config.yaml；Embedding→平台模型 + .env key)。
    Embedding 为双轨私有侧：租户只 BYO api_key，base_url/model/dimension 锁平台(见 ADR 003)。
    """
    tenant_id: str = ""  # 租户id(主键)
    llm_config: Optional[LLMConfig] = None  # 组织自定义LLM配置，None表示未覆盖
    embed_config: Optional[EmbedConfig] = None  # 组织自定义Embedding配置(仅api_key生效)，None表示未覆盖
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
