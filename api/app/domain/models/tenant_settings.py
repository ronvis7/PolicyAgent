from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.models.app_config import EmbedConfig, LLMConfig


class FeishuNotifyConfig(BaseModel):
    """飞书群自定义机器人 webhook 配置(组织级"新赛事即推"的推送目标)。

    secret 为空表示该机器人未开启签名校验。
    """
    webhook_url: str = ""
    secret: str = ""


class TenantSettings(BaseModel):
    """租户级设置领域模型，承载组织对平台默认配置的覆盖。

    承载 LLM 与 Embedding 配置覆盖(BYO key)：对应字段为 None 表示该组织未自定义，
    运行时回落到平台默认配置(LLM→config.yaml；Embedding→平台模型 + .env key)。
    Embedding 为双轨私有侧：租户只 BYO api_key，base_url/model/dimension 锁平台(见 ADR 003)。
    飞书推送配置为 None 表示该组织未开启新赛事推送。
    """
    tenant_id: str = ""  # 租户id(主键)
    llm_config: Optional[LLMConfig] = None  # 组织自定义LLM配置，None表示未覆盖
    embed_config: Optional[EmbedConfig] = None  # 组织自定义Embedding配置(仅api_key生效)，None表示未覆盖
    feishu_config: Optional[FeishuNotifyConfig] = None  # 组织飞书群webhook(新赛事即推)，None表示未开启
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
