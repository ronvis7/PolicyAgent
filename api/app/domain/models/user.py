import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"  # 正常
    DISABLED = "disabled"  # 已禁用


class User(BaseModel):
    """用户领域模型，全局身份，可通过membership属于多个租户"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 用户id
    email: str = ""  # 邮箱(全局唯一登录标识)
    password_hash: str = ""  # argon2密码哈希
    display_name: str = ""  # 显示名称
    status: UserStatus = UserStatus.ACTIVE  # 状态
    is_platform_admin: bool = False  # 是否为平台管理员(可管理平台级配置)
    last_login_at: Optional[datetime] = None  # 最后登录时间
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
