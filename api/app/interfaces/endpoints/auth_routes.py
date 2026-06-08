import logging

from fastapi import APIRouter, Depends

from app.application.services.auth_service import AuthResult, AuthService
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas import Response
from app.interfaces.schemas.auth import (
    AuthData,
    LoginRequest,
    LogoutRequest,
    MeData,
    RefreshRequest,
    RegisterRequest,
    SwitchTenantRequest,
    TenantInfo,
    UserInfo,
)
from app.interfaces.service_dependencies import get_auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证模块"])


def _to_auth_data(result: AuthResult) -> AuthData:
    """将AuthResult领域结果映射为接口层AuthData"""
    return AuthData(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        user=UserInfo(id=result.user.id, email=result.user.email, display_name=result.user.display_name),
        active_tenant_id=result.active_tenant.id,
        role=result.role,
        tenants=[_to_tenant_info(t) for t in result.tenants],
    )


def _to_tenant_info(tenant) -> TenantInfo:
    """将Tenant领域模型映射为TenantInfo"""
    return TenantInfo(id=tenant.id, name=tenant.name, slug=tenant.slug, plan=tenant.plan.value)


@router.post(
    path="/register",
    response_model=Response[AuthData],
    summary="注册新用户与组织",
    description="创建用户并自动创建其归属的组织(注册者成为owner)",
)
async def register(
        request: RegisterRequest,
        auth_service: AuthService = Depends(get_auth_service),
) -> Response[AuthData]:
    result = await auth_service.register(
        email=request.email,
        password=request.password,
        display_name=request.display_name,
        org_name=request.org_name,
    )
    return Response.success(msg="注册成功", data=_to_auth_data(result))


@router.post(
    path="/login",
    response_model=Response[AuthData],
    summary="登录",
    description="校验邮箱密码并签发令牌，默认激活第一个组织",
)
async def login(
        request: LoginRequest,
        auth_service: AuthService = Depends(get_auth_service),
) -> Response[AuthData]:
    result = await auth_service.login(email=request.email, password=request.password)
    return Response.success(msg="登录成功", data=_to_auth_data(result))


@router.post(
    path="/refresh",
    response_model=Response[AuthData],
    summary="刷新令牌",
    description="用refresh令牌轮换出新的令牌对(旧refresh令牌失效)",
)
async def refresh(
        request: RefreshRequest,
        auth_service: AuthService = Depends(get_auth_service),
) -> Response[AuthData]:
    result = await auth_service.refresh(refresh_token=request.refresh_token)
    return Response.success(msg="刷新成功", data=_to_auth_data(result))


@router.post(
    path="/logout",
    response_model=Response[dict],
    summary="登出",
    description="吊销refresh令牌",
)
async def logout(
        request: LogoutRequest,
        auth_service: AuthService = Depends(get_auth_service),
) -> Response[dict]:
    await auth_service.logout(refresh_token=request.refresh_token)
    return Response.success(msg="登出成功")


@router.post(
    path="/switch-tenant",
    response_model=Response[AuthData],
    summary="切换当前组织",
    description="切换激活组织并重新签发令牌(需要对目标组织有有效成员关系)",
)
async def switch_tenant(
        request: SwitchTenantRequest,
        current_user: CurrentUser = Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
) -> Response[AuthData]:
    result = await auth_service.switch_tenant(
        user_id=current_user.user_id,
        target_tenant_id=request.tenant_id,
    )
    return Response.success(msg="切换组织成功", data=_to_auth_data(result))


@router.get(
    path="/me",
    response_model=Response[MeData],
    summary="获取当前登录上下文",
    description="返回当前用户、激活组织、角色与可访问组织列表",
)
async def me(
        current_user: CurrentUser = Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
) -> Response[MeData]:
    result = await auth_service.get_context(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )
    data = MeData(
        user=UserInfo(id=result.user.id, email=result.user.email, display_name=result.user.display_name),
        active_tenant_id=result.active_tenant.id,
        role=result.role,
        tenants=[_to_tenant_info(t) for t in result.tenants],
    )
    return Response.success(msg="获取成功", data=data)
