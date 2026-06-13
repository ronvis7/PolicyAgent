from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.models.app_config import LLMConfig


class TenantSettings(BaseModel):
    """租户级设置领域模型，承载组织对平台默认配置的覆盖。

    目前仅承载 LLM 配置覆盖(BYO key)：llm_config 为 None 表示该组织未自定义，
    运行时回落到平台默认配置(config.yaml)。
    """
    tenant_id: str = ""  # 租户id(主键)
    llm_config: Optional[LLMConfig] = None  # 组织自定义LLM配置，None表示未覆盖
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
