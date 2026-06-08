import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MembershipRole(str, Enum):
    """成员角色枚举"""
    OWNER = "owner"  # 拥有者(创建组织者)
    ADMIN = "admin"  # 管理员
    MEMBER = "member"  # 普通成员


class MembershipStatus(str, Enum):
    """成员关系状态枚举"""
    ACTIVE = "active"  # 已加入
    INVITED = "invited"  # 已邀请待接受
    DISABLED = "disabled"  # 已移除/禁用


class Membership(BaseModel):
    """成员关系领域模型，用户与租户的多对多关联并携带角色"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 成员关系id
    user_id: str = ""  # 用户id
    tenant_id: str = ""  # 租户id
    role: MembershipRole = MembershipRole.MEMBER  # 角色
    status: MembershipStatus = MembershipStatus.ACTIVE  # 状态
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
