from typing import Callable, Optional

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.application.errors.exceptions import ForbiddenError, UnauthorizedError
from app.domain.external.token_service import TokenService
from app.interfaces.service_dependencies import get_token_service

# access令牌类型标识
TOKEN_TYPE_ACCESS = "access"

# HTTP Bearer认证方案(auto_error=False以便统一抛出业务异常)
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """当前请求的认证主体，来源于access令牌claims(无需查库)"""
    user_id: str
    tenant_id: str
    role: str


async def get_current_claims(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        token_service: TokenService = Depends(get_token_service),
) -> dict:
    """解析并校验access令牌，返回claims"""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("请先登录")
    claims = token_service.decode(credentials.credentials)
    if claims.get("type") != TOKEN_TYPE_ACCESS:
        raise UnauthorizedError("无效的访问令牌")
    return claims


async def get_current_user(claims: dict = Depends(get_current_claims)) -> CurrentUser:
    """从claims构建当前认证主体(用户id + 激活租户id + 角色)"""
    user_id = claims.get("sub")
    tenant_id = claims.get("tid")
    if not user_id or not tenant_id:
        raise UnauthorizedError("无效的访问令牌")
    return CurrentUser(user_id=user_id, tenant_id=tenant_id, role=claims.get("role", ""))


def require_role(*roles: str) -> Callable[..., "CurrentUser"]:
    """角色校验依赖工厂，要求当前主体角色在允许列表内"""

    async def checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise ForbiddenError("无权执行该操作")
        return current_user

    return checker
