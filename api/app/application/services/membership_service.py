"""组织成员管理服务：列出成员、按邮箱添加已注册用户、变更角色、移除成员。

权限边界由接口层 require_role(owner/admin) 把控；本服务在此之上做业务规则约束：
owner 角色不可经接口变更或移除(仅注册时设定)，可赋予的角色仅 admin/member。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from app.application.errors.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.domain.models.membership import Membership, MembershipRole, MembershipStatus
from app.domain.models.user import User
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)

# 可经接口分配的角色(owner 仅注册时产生，不可经接口赋予)
ASSIGNABLE_ROLES = {MembershipRole.ADMIN, MembershipRole.MEMBER}


@dataclass(frozen=True)
class MemberView:
    """成员视图，聚合成员关系与用户基本信息"""
    membership_id: str
    user_id: str
    email: str
    display_name: str
    role: str
    status: str
    created_at: datetime


class MembershipService:
    """组织成员管理服务"""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def list_members(self, tenant_id: str) -> List[MemberView]:
        """列出某组织的全部有效成员(按加入时间升序)"""
        async with self.uow_factory() as uow:
            memberships = await uow.membership.list_by_tenant(tenant_id)
            views: List[MemberView] = []
            for membership in memberships:
                if membership.status == MembershipStatus.DISABLED:
                    continue
                user = await uow.user.get_by_id(membership.user_id)
                if user is None:
                    continue
                views.append(self._to_view(membership, user))
        return views

    async def add_member_by_email(
            self,
            tenant_id: str,
            email: str,
            role: MembershipRole,
    ) -> MemberView:
        """按邮箱将一名已注册用户加入组织"""
        self._ensure_assignable(role)
        normalized = email.strip().lower()
        async with self.uow_factory() as uow:
            # 1.目标用户必须已注册
            user = await uow.user.get_by_email(normalized)
            if user is None:
                raise NotFoundError("该邮箱尚未注册，请对方先注册账号后再添加")

            # 2.已是有效成员则冲突；曾被移除则复用记录重新激活
            existing = await uow.membership.get_by_user_and_tenant(user.id, tenant_id)
            if existing is not None and existing.status == MembershipStatus.ACTIVE:
                raise ConflictError("该用户已是本组织成员")

            membership = self._build_membership(existing, user.id, tenant_id, role)
            await uow.membership.save(membership)
            view = self._to_view(membership, user)
        return view

    async def change_role(
            self,
            tenant_id: str,
            membership_id: str,
            role: MembershipRole,
    ) -> MemberView:
        """变更某成员的角色(不可变更 owner，不可设为 owner)"""
        self._ensure_assignable(role)
        async with self.uow_factory() as uow:
            membership, user = await self._load_member(uow, tenant_id, membership_id)
            if membership.role == MembershipRole.OWNER:
                raise ForbiddenError("不能变更组织所有者的角色")

            updated = membership.model_copy(update={"role": role, "updated_at": datetime.now()})
            await uow.membership.save(updated)
            view = self._to_view(updated, user)
        return view

    async def remove_member(self, tenant_id: str, membership_id: str) -> None:
        """移除某成员(软删除为 disabled；不可移除 owner)"""
        async with self.uow_factory() as uow:
            membership, _ = await self._load_member(uow, tenant_id, membership_id)
            if membership.role == MembershipRole.OWNER:
                raise ForbiddenError("不能移除组织所有者")

            disabled = membership.model_copy(
                update={"status": MembershipStatus.DISABLED, "updated_at": datetime.now()}
            )
            await uow.membership.save(disabled)

    # ==================== 内部辅助方法 ====================

    @staticmethod
    def _ensure_assignable(role: MembershipRole) -> None:
        """校验角色可经接口分配"""
        if role not in ASSIGNABLE_ROLES:
            raise ForbiddenError("只能将成员设置为管理员或普通成员")

    @staticmethod
    def _build_membership(
            existing: Optional[Membership],
            user_id: str,
            tenant_id: str,
            role: MembershipRole,
    ) -> Membership:
        """新建成员关系，或复用既有(被禁用)记录重新激活"""
        if existing is not None:
            return existing.model_copy(
                update={
                    "role": role,
                    "status": MembershipStatus.ACTIVE,
                    "updated_at": datetime.now(),
                }
            )
        return Membership(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            status=MembershipStatus.ACTIVE,
        )

    @staticmethod
    async def _load_member(
            uow: IUnitOfWork,
            tenant_id: str,
            membership_id: str,
    ) -> tuple[Membership, User]:
        """按 membership_id 在本组织范围内加载成员关系与用户(隔离他租户)"""
        memberships = await uow.membership.list_by_tenant(tenant_id)
        membership = next((m for m in memberships if m.id == membership_id), None)
        if membership is None or membership.status == MembershipStatus.DISABLED:
            raise NotFoundError("成员不存在或已被移除")
        user = await uow.user.get_by_id(membership.user_id)
        if user is None:
            raise NotFoundError("成员对应的用户不存在")
        return membership, user

    @staticmethod
    def _to_view(membership: Membership, user: User) -> MemberView:
        """聚合成员关系与用户为成员视图"""
        return MemberView(
            membership_id=membership.id,
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role.value,
            status=membership.status.value,
            created_at=membership.created_at,
        )
