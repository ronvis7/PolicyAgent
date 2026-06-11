import json
import logging
import re
import secrets
from datetime import datetime
from typing import Callable, List

from pydantic import BaseModel

from app.application.errors.exceptions import (
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from app.domain.external.password_hasher import PasswordHasher
from app.domain.external.token_service import TokenService
from app.domain.models.membership import Membership, MembershipRole, MembershipStatus
from app.domain.models.tenant import Tenant, TenantPlan
from app.domain.models.user import User, UserStatus
from app.domain.repositories.uow import IUnitOfWork
from app.infrastructure.storage.redis import RedisClient

logger = logging.getLogger(__name__)

# Redis中refresh令牌白名单的key前缀
REFRESH_TOKEN_PREFIX = "auth:refresh:"
# refresh令牌类型标识
TOKEN_TYPE_REFRESH = "refresh"


class TokenPair(BaseModel):
    """access/refresh令牌对"""
    access_token: str
    refresh_token: str


class AuthResult(BaseModel):
    """认证结果，包含用户、激活租户、角色、可访问租户列表与令牌"""
    user: User
    active_tenant: Tenant
    role: str
    tenants: List[Tenant]
    tokens: TokenPair


class AuthService:
    """认证服务，负责注册/登录/刷新/登出/切换租户"""

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],
            password_hasher: PasswordHasher,
            token_service: TokenService,
            redis_client: RedisClient,
            refresh_token_ttl_seconds: int,
    ) -> None:
        self.uow_factory = uow_factory
        self.password_hasher = password_hasher
        self.token_service = token_service
        self.redis_client = redis_client
        self.refresh_token_ttl_seconds = refresh_token_ttl_seconds

    async def register(
            self,
            email: str,
            password: str,
            display_name: str,
            org_name: str,
    ) -> AuthResult:
        """注册：创建用户 + 组织 + owner成员关系，并签发令牌"""
        email = self._normalize_email(email)
        async with self.uow_factory() as uow:
            # 1.邮箱唯一性校验
            if await uow.user.get_by_email(email):
                raise ConflictError("该邮箱已注册，请直接登录")

            # 2.创建租户(组织)
            base_name = org_name.strip() or f"{display_name or email.split('@')[0]} 的组织"
            slug = await self._generate_unique_slug(uow, org_name or display_name or email.split("@")[0])
            tenant = Tenant(name=base_name, slug=slug, plan=TenantPlan.FREE)
            await uow.tenant.save(tenant)

            # 3.创建用户
            user = User(
                email=email,
                password_hash=self.password_hasher.hash(password),
                display_name=display_name.strip() or email.split("@")[0],
            )
            await uow.user.save(user)

            # 4.先flush租户与用户，确保父行已写入，避免membership外键约束失败
            await uow.flush()

            # 5.创建owner成员关系
            membership = Membership(
                user_id=user.id,
                tenant_id=tenant.id,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
            await uow.membership.save(membership)

        # 6.事务提交后签发令牌
        tokens = await self._issue_tokens(user.id, tenant.id, MembershipRole.OWNER.value)
        return AuthResult(
            user=user,
            active_tenant=tenant,
            role=MembershipRole.OWNER.value,
            tenants=[tenant],
            tokens=tokens,
        )

    async def login(self, email: str, password: str) -> AuthResult:
        """登录：校验密码，默认激活第一个组织并签发令牌"""
        email = self._normalize_email(email)
        async with self.uow_factory() as uow:
            # 1.查询用户并校验状态
            user = await uow.user.get_by_email(email)
            if user is None or user.status != UserStatus.ACTIVE:
                raise UnauthorizedError("邮箱或密码错误")

            # 2.校验密码
            if not self.password_hasher.verify(password, user.password_hash):
                raise UnauthorizedError("邮箱或密码错误")

            # 3.查询可访问的组织
            active_memberships = await self._list_active_memberships(uow, user.id)
            if not active_memberships:
                raise ForbiddenError("当前账号尚未加入任何组织")
            primary = active_memberships[0]
            tenants = await self._load_tenants(uow, active_memberships)
            active_tenant = next(t for t in tenants if t.id == primary.tenant_id)

            # 4.更新最后登录时间
            user.last_login_at = datetime.now()
            await uow.user.save(user)
            role = primary.role.value

        tokens = await self._issue_tokens(user.id, active_tenant.id, role)
        return AuthResult(user=user, active_tenant=active_tenant, role=role, tenants=tenants, tokens=tokens)

    async def refresh(self, refresh_token: str) -> AuthResult:
        """用refresh令牌轮换出新的令牌对"""
        # 1.解析并校验令牌类型
        claims = self.token_service.decode(refresh_token)
        if claims.get("type") != TOKEN_TYPE_REFRESH:
            raise UnauthorizedError("无效的刷新令牌")

        # 2.校验Redis白名单(支持吊销)
        jti = claims.get("jti", "")
        key = f"{REFRESH_TOKEN_PREFIX}{jti}"
        data = await self.redis_client.client.get(key)
        if not data:
            raise UnauthorizedError("登录状态已失效，请重新登录")
        stored = json.loads(data)
        user_id, tenant_id = stored["user_id"], stored["tenant_id"]

        async with self.uow_factory() as uow:
            # 3.校验用户与成员关系仍有效
            user = await uow.user.get_by_id(user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                raise UnauthorizedError("登录状态已失效，请重新登录")
            membership = await uow.membership.get_by_user_and_tenant(user_id, tenant_id)
            if membership is None or membership.status != MembershipStatus.ACTIVE:
                raise UnauthorizedError("组织访问权限已变更，请重新登录")
            tenants = await self._load_tenants(uow, await self._list_active_memberships(uow, user_id))
            active_tenant = next(t for t in tenants if t.id == tenant_id)
            role = membership.role.value

        # 4.轮换：删除旧jti并签发新令牌对
        await self.redis_client.client.delete(key)
        tokens = await self._issue_tokens(user_id, tenant_id, role)
        return AuthResult(user=user, active_tenant=active_tenant, role=role, tenants=tenants, tokens=tokens)

    async def logout(self, refresh_token: str) -> None:
        """登出：从白名单删除refresh令牌"""
        try:
            claims = self.token_service.decode(refresh_token)
        except UnauthorizedError:
            # 令牌本身已失效，无需再吊销
            return
        jti = claims.get("jti")
        if jti:
            await self.redis_client.client.delete(f"{REFRESH_TOKEN_PREFIX}{jti}")

    async def switch_tenant(self, user_id: str, target_tenant_id: str) -> AuthResult:
        """切换当前激活组织，重新签发携带新租户的令牌对"""
        async with self.uow_factory() as uow:
            # 1.校验目标组织的成员关系有效
            membership = await uow.membership.get_by_user_and_tenant(user_id, target_tenant_id)
            if membership is None or membership.status != MembershipStatus.ACTIVE:
                raise ForbiddenError("无权访问该组织")
            user = await uow.user.get_by_id(user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                raise UnauthorizedError("登录状态已失效，请重新登录")
            tenants = await self._load_tenants(uow, await self._list_active_memberships(uow, user_id))
            active_tenant = next(t for t in tenants if t.id == target_tenant_id)
            role = membership.role.value

        tokens = await self._issue_tokens(user_id, target_tenant_id, role)
        return AuthResult(user=user, active_tenant=active_tenant, role=role, tenants=tenants, tokens=tokens)

    async def get_context(self, user_id: str, tenant_id: str) -> AuthResult:
        """获取当前登录上下文(/auth/me)，不签发新令牌"""
        async with self.uow_factory() as uow:
            user = await uow.user.get_by_id(user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                raise UnauthorizedError("登录状态已失效，请重新登录")
            membership = await uow.membership.get_by_user_and_tenant(user_id, tenant_id)
            if membership is None or membership.status != MembershipStatus.ACTIVE:
                raise UnauthorizedError("组织访问权限已变更，请重新登录")
            tenants = await self._load_tenants(uow, await self._list_active_memberships(uow, user_id))
            active_tenant = next(t for t in tenants if t.id == tenant_id)
            role = membership.role.value

        return AuthResult(
            user=user,
            active_tenant=active_tenant,
            role=role,
            tenants=tenants,
            tokens=TokenPair(access_token="", refresh_token=""),
        )

    async def is_platform_admin(self, user_id: str) -> bool:
        """判断用户是否为平台管理员"""
        async with self.uow_factory() as uow:
            user = await uow.user.get_by_id(user_id)
        return user is not None and user.is_platform_admin

    # ==================== 内部辅助方法 ====================

    async def _issue_tokens(self, user_id: str, tenant_id: str, role: str) -> TokenPair:
        """签发令牌对并将refresh令牌的jti写入Redis白名单"""
        access_token = self.token_service.create_access_token(user_id, tenant_id, role)
        refresh_token = self.token_service.create_refresh_token(user_id, tenant_id)
        jti = self.token_service.decode(refresh_token).get("jti", "")
        await self.redis_client.client.set(
            f"{REFRESH_TOKEN_PREFIX}{jti}",
            json.dumps({"user_id": user_id, "tenant_id": tenant_id}),
            ex=self.refresh_token_ttl_seconds,
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    @staticmethod
    async def _list_active_memberships(uow: IUnitOfWork, user_id: str) -> List[Membership]:
        """获取用户所有处于active状态的成员关系"""
        memberships = await uow.membership.list_by_user(user_id)
        return [m for m in memberships if m.status == MembershipStatus.ACTIVE]

    @staticmethod
    async def _load_tenants(uow: IUnitOfWork, memberships: List[Membership]) -> List[Tenant]:
        """根据成员关系批量加载租户"""
        tenants: List[Tenant] = []
        for membership in memberships:
            tenant = await uow.tenant.get_by_id(membership.tenant_id)
            if tenant is not None:
                tenants.append(tenant)
        return tenants

    @staticmethod
    def _normalize_email(email: str) -> str:
        """标准化邮箱(去空格+小写)"""
        return email.strip().lower()

    async def _generate_unique_slug(self, uow: IUnitOfWork, raw: str) -> str:
        """根据名称生成唯一slug，冲突时追加随机短码"""
        base = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-") or "org"
        slug = base
        while await uow.tenant.get_by_slug(slug) is not None:
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug
