"""AuthService.register 离线单元测试：创建组织 / 加入组织(含个人工作区与 pending 申请)。"""

import asyncio
import json

import pytest

from app.application.errors.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.application.services.auth_service import AuthService
from app.domain.models.membership import MembershipRole, MembershipStatus
from app.domain.models.tenant import Tenant

from ._fakes import make_uow_factory


class _FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class _FakeTokenService:
    def create_access_token(self, user_id: str, tenant_id: str, role: str) -> str:
        return "access-token"

    def create_refresh_token(self, user_id: str, tenant_id: str) -> str:
        return "refresh-token"

    def decode(self, token: str) -> dict:
        return {"jti": "jti-x", "type": "refresh"}


class _FakeRedisInner:
    async def set(self, *args, **kwargs) -> None: ...
    async def get(self, *args, **kwargs):
        return None
    async def delete(self, *args, **kwargs) -> None: ...


class _FakeRedis:
    def __init__(self) -> None:
        self.client = _FakeRedisInner()


def _service(tenants=None, memberships=None, users=None):
    factory = make_uow_factory(
        users=users if users is not None else {},
        memberships=memberships if memberships is not None else {},
        tenants=tenants if tenants is not None else {},
    )
    return AuthService(
        uow_factory=factory,
        password_hasher=_FakeHasher(),
        token_service=_FakeTokenService(),
        redis_client=_FakeRedis(),
        refresh_token_ttl_seconds=3600,
    )


def test_create_org_makes_owner() -> None:
    service = _service()

    result = asyncio.run(service.register(
        email="a@x.com", password="password1", display_name="A",
        mode="create", org_name="重庆理工大学",
    ))

    assert result.role == MembershipRole.OWNER.value
    assert result.active_tenant.name == "重庆理工大学"
    assert result.active_tenant.is_personal is False
    assert [t.id for t in result.tenants] == [result.active_tenant.id]


def test_create_org_duplicate_name_conflicts() -> None:
    existing = Tenant(name="重庆理工大学", slug="cqut", is_personal=False)
    service = _service(tenants={existing.id: existing})

    with pytest.raises(ConflictError):
        asyncio.run(service.register(
            email="b@x.com", password="password1", display_name="B",
            mode="create", org_name="  重庆理工大学  ",  # 规范化后同名
        ))


def test_create_org_empty_name_rejected() -> None:
    service = _service()

    with pytest.raises(BadRequestError):
        asyncio.run(service.register(
            email="c@x.com", password="password1", display_name="C",
            mode="create", org_name="   ",
        ))


def test_join_org_creates_personal_workspace_and_pending() -> None:
    target = Tenant(name="重庆理工大学", slug="cqut", is_personal=False)
    memberships: dict = {}
    service = _service(tenants={target.id: target}, memberships=memberships)

    result = asyncio.run(service.register(
        email="d@x.com", password="password1", display_name="Dave",
        mode="join", org_id=target.id,
    ))

    # 激活租户是个人工作区，注册者为 owner
    assert result.active_tenant.is_personal is True
    assert result.role == MembershipRole.OWNER.value
    assert [t.id for t in result.tenants] == [result.active_tenant.id]

    # 对目标组织生成了 pending 申请
    pending = [m for m in memberships.values()
               if m.tenant_id == target.id and m.status == MembershipStatus.PENDING]
    assert len(pending) == 1


def test_join_nonexistent_org_raises() -> None:
    service = _service()

    with pytest.raises(NotFoundError):
        asyncio.run(service.register(
            email="e@x.com", password="password1", display_name="E",
            mode="join", org_id="no-such-org",
        ))


def test_join_personal_workspace_not_allowed_as_target() -> None:
    personal = Tenant(name="某人的工作区", slug="ws", is_personal=True)
    service = _service(tenants={personal.id: personal})

    with pytest.raises(NotFoundError):
        asyncio.run(service.register(
            email="f@x.com", password="password1", display_name="F",
            mode="join", org_id=personal.id,
        ))


def test_duplicate_email_conflicts() -> None:
    target = Tenant(name="组织X", slug="x", is_personal=False)
    service = _service(tenants={target.id: target})
    asyncio.run(service.register(
        email="g@x.com", password="password1", display_name="G",
        mode="create", org_name="组织Y",
    ))

    with pytest.raises(ConflictError):
        asyncio.run(service.register(
            email="g@x.com", password="password1", display_name="G2",
            mode="create", org_name="组织Z",
        ))
