from typing import List

from pydantic import BaseModel, Field

# 邮箱格式校验正则(避免引入email-validator依赖)
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    """注册请求"""
    email: str = Field(pattern=EMAIL_PATTERN, description="邮箱")
    password: str = Field(min_length=8, max_length=128, description="密码(至少8位)")
    display_name: str = Field(default="", max_length=255, description="显示名称")
    org_name: str = Field(default="", max_length=255, description="组织名称")


class LoginRequest(BaseModel):
    """登录请求"""
    email: str = Field(pattern=EMAIL_PATTERN, description="邮箱")
    password: str = Field(min_length=1, description="密码")


class RefreshRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str = Field(description="刷新令牌")


class LogoutRequest(BaseModel):
    """登出请求"""
    refresh_token: str = Field(description="刷新令牌")


class SwitchTenantRequest(BaseModel):
    """切换组织请求"""
    tenant_id: str = Field(description="目标组织id")


class UserInfo(BaseModel):
    """用户信息"""
    id: str
    email: str
    display_name: str


class TenantInfo(BaseModel):
    """组织信息"""
    id: str
    name: str
    slug: str
    plan: str


class AuthData(BaseModel):
    """认证成功返回的数据(注册/登录/刷新/切换组织)"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo
    active_tenant_id: str
    role: str
    tenants: List[TenantInfo]


class MeData(BaseModel):
    """当前登录上下文(/auth/me)"""
    user: UserInfo
    active_tenant_id: str
    role: str
    tenants: List[TenantInfo]
