import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TenantStatus(str, Enum):
    """租户状态枚举"""
    ACTIVE = "active"  # 正常
    SUSPENDED = "suspended"  # 已停用


class TenantPlan(str, Enum):
    """租户套餐枚举"""
    FREE = "free"  # 免费版
    PRO = "pro"  # 专业版
    ENTERPRISE = "enterprise"  # 企业版


class Tenant(BaseModel):
    """租户(组织)领域模型，多租户系统中的隔离边界"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 租户id
    name: str = ""  # 租户名称(组织名)
    slug: str = ""  # 唯一标识，未来用于子域名/URL
    plan: TenantPlan = TenantPlan.FREE  # 套餐
    status: TenantStatus = TenantStatus.ACTIVE  # 状态
    monthly_token_limit: int = 0  # 月度token配额，0表示不限制
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
