from typing import List, Literal

from pydantic import BaseModel, Field

# 邮箱格式校验正则(避免引入email-validator依赖)
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    """注册请求。

    mode="create"：填 org_name 创建新组织(注册者为 owner)。
    mode="join"：填 org_id 申请加入已有组织(待审批，先在个人工作区使用)。
    """
    email: str = Field(pattern=EMAIL_PATTERN, description="邮箱")
    password: str = Field(min_length=8, max_length=128, description="密码(至少8位)")
    display_name: str = Field(default="", max_length=255, description="显示名称")
    mode: Literal["create", "join"] = Field(default="create", description="注册模式")
    org_name: str = Field(default="", max_length=255, description="组织名称(创建模式)")
    org_id: str = Field(default="", max_length=255, description="目标组织id(加入模式)")


class OrgOption(BaseModel):
    """可加入的组织选项(注册页选择用)"""
    id: str
    name: str


class ListOrgsResponse(BaseModel):
    """可加入组织列表响应"""
    orgs: List[OrgOption] = Field(default_factory=list)


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
    is_platform_admin: bool = False


class TenantInfo(BaseModel):
    """组织信息"""
    id: str
    name: str
    slug: str
    plan: str
    is_personal: bool = False  # 个人工作区(join 未获批前的临时空间)，供前端给出提示


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
