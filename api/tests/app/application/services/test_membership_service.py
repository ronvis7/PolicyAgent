"""MembershipService 离线单元测试：列表/按邮箱添加/改角色/移除 + 业务规则。

异步方法用 asyncio.run 驱动，避免依赖 pytest-asyncio 插件(与本仓库其他测试一致)。
"""

import asyncio

import pytest

from app.application.errors.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.application.services.membership_service import MembershipService
from app.domain.models.membership import Membership, MembershipRole, MembershipStatus
from app.domain.models.user import User

from ._fakes import make_uow_factory

TENANT = "tenant-1"


def _seed():
    """构造：owner(已在组织) + 一个待添加的已注册用户 bob + 一个组织内 member carol"""
    owner = User(id="u-owner", email="owner@x.com", display_name="Owner")
    bob = User(id="u-bob", email="bob@x.com", display_name="Bob")
    carol = User(id="u-carol", email="carol@x.com", display_name="Carol")
    users = {u.id: u for u in (owner, bob, carol)}

    owner_m = Membership(id="m-owner", user_id=owner.id, tenant_id=TENANT, role=MembershipRole.OWNER)
    carol_m = Membership(id="m-carol", user_id=carol.id, tenant_id=TENANT, role=MembershipRole.MEMBER)
    memberships = {owner_m.id: owner_m, carol_m.id: carol_m}

    factory = make_uow_factory(users=users, memberships=memberships)
    return MembershipService(uow_factory=factory), users, memberships


def test_list_members_excludes_disabled() -> None:
    service, _, memberships = _seed()
    memberships["m-carol"] = memberships["m-carol"].model_copy(
        update={"status": MembershipStatus.DISABLED}
    )

    members = asyncio.run(service.list_members(TENANT))

    assert {m.email for m in members} == {"owner@x.com"}


def test_add_member_by_email_success() -> None:
    service, _, _ = _seed()

    view = asyncio.run(service.add_member_by_email(TENANT, "bob@x.com", MembershipRole.MEMBER))

    assert view.email == "bob@x.com"
    assert view.role == "member"
    members = asyncio.run(service.list_members(TENANT))
    assert "bob@x.com" in {m.email for m in members}


def test_add_member_unregistered_email_raises() -> None:
    service, _, _ = _seed()

    with pytest.raises(NotFoundError):
        asyncio.run(service.add_member_by_email(TENANT, "ghost@x.com", MembershipRole.MEMBER))


def test_add_existing_active_member_conflicts() -> None:
    service, _, _ = _seed()

    with pytest.raises(ConflictError):
        asyncio.run(service.add_member_by_email(TENANT, "carol@x.com", MembershipRole.MEMBER))


def test_add_member_as_owner_role_rejected() -> None:
    service, _, _ = _seed()

    with pytest.raises(ForbiddenError):
        asyncio.run(service.add_member_by_email(TENANT, "bob@x.com", MembershipRole.OWNER))


def test_change_role_promotes_member_to_admin() -> None:
    service, _, _ = _seed()

    view = asyncio.run(service.change_role(TENANT, "m-carol", MembershipRole.ADMIN))

    assert view.role == "admin"


def test_change_role_on_owner_forbidden() -> None:
    service, _, _ = _seed()

    with pytest.raises(ForbiddenError):
        asyncio.run(service.change_role(TENANT, "m-owner", MembershipRole.MEMBER))


def test_change_role_other_tenant_membership_not_found() -> None:
    service, _, _ = _seed()

    with pytest.raises(NotFoundError):
        asyncio.run(service.change_role("other-tenant", "m-carol", MembershipRole.ADMIN))


def test_remove_member_soft_deletes() -> None:
    service, _, _ = _seed()

    asyncio.run(service.remove_member(TENANT, "m-carol"))

    members = asyncio.run(service.list_members(TENANT))
    assert "carol@x.com" not in {m.email for m in members}


def test_remove_owner_forbidden() -> None:
    service, _, _ = _seed()

    with pytest.raises(ForbiddenError):
        asyncio.run(service.remove_member(TENANT, "m-owner"))


def test_readd_removed_member_reactivates() -> None:
    service, _, _ = _seed()
    asyncio.run(service.remove_member(TENANT, "m-carol"))

    view = asyncio.run(service.add_member_by_email(TENANT, "carol@x.com", MembershipRole.ADMIN))

    assert view.role == "admin"
    assert view.status == "active"
