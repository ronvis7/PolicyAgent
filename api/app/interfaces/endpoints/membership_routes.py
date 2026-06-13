"""组织成员管理路由：列出成员、按邮箱添加、变更角色、移除。

列表对任意有效成员开放；增删改仅限组织 owner/admin。所有操作均作用于当前
登录令牌中的激活租户，天然隔离其他组织。
"""

import logging

from fastapi import APIRouter, Depends

from app.application.services.membership_service import MemberView, MembershipService
from app.domain.models.membership import MembershipRole
from app.interfaces.auth_dependencies import CurrentUser, get_current_user, require_role
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.membership import (
    AddMemberRequest,
    ChangeRoleRequest,
    ListMembersResponse,
    MemberItem,
)
from app.interfaces.service_dependencies import get_membership_service

logger = logging.getLogger(__name__)

# 增删改仅限组织 owner/admin
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)

router = APIRouter(prefix="/members", tags=["成员管理"])


def _to_item(view: MemberView) -> MemberItem:
    """将成员视图映射为接口层条目"""
    return MemberItem(
        membership_id=view.membership_id,
        user_id=view.user_id,
        email=view.email,
        display_name=view.display_name,
        role=view.role,
        status=view.status,
        created_at=view.created_at,
    )


@router.get(
    path="",
    response_model=Response[ListMembersResponse],
    summary="获取当前组织成员列表",
    description="返回当前组织的全部有效成员(对任意有效成员开放)",
)
async def list_members(
        current_user: CurrentUser = Depends(get_current_user),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[ListMembersResponse]:
    """获取当前组织成员列表"""
    views = await membership_service.list_members(current_user.tenant_id)
    return Response.success(data=ListMembersResponse(members=[_to_item(v) for v in views]))


@router.get(
    path="/requests",
    response_model=Response[ListMembersResponse],
    summary="获取待审批的加入申请",
    description="返回当前组织 pending 状态的加入申请(仅 owner/admin)",
)
async def list_requests(
        current_user: CurrentUser = Depends(_require_org_admin),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[ListMembersResponse]:
    """获取待审批的加入申请"""
    views = await membership_service.list_pending_requests(current_user.tenant_id)
    return Response.success(data=ListMembersResponse(members=[_to_item(v) for v in views]))


@router.post(
    path="/{membership_id}/approve",
    response_model=Response[MemberItem],
    summary="批准加入申请",
    description="批准一条 pending 加入申请，成员转为正式成员(仅 owner/admin)",
)
async def approve_request(
        membership_id: str,
        current_user: CurrentUser = Depends(_require_org_admin),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[MemberItem]:
    """批准加入申请"""
    view = await membership_service.approve_request(
        tenant_id=current_user.tenant_id,
        membership_id=membership_id,
    )
    return Response.success(msg="已批准加入申请", data=_to_item(view))


@router.post(
    path="/{membership_id}/reject",
    response_model=Response[dict],
    summary="拒绝加入申请",
    description="拒绝一条 pending 加入申请(仅 owner/admin)",
)
async def reject_request(
        membership_id: str,
        current_user: CurrentUser = Depends(_require_org_admin),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[dict]:
    """拒绝加入申请"""
    await membership_service.reject_request(
        tenant_id=current_user.tenant_id,
        membership_id=membership_id,
    )
    return Response.success(msg="已拒绝加入申请")


@router.post(
    path="",
    response_model=Response[MemberItem],
    summary="按邮箱添加成员",
    description="将一名已注册用户加入当前组织(仅 owner/admin)",
)
async def add_member(
        request: AddMemberRequest,
        current_user: CurrentUser = Depends(_require_org_admin),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[MemberItem]:
    """按邮箱添加成员"""
    view = await membership_service.add_member_by_email(
        tenant_id=current_user.tenant_id,
        email=request.email,
        role=request.role,
    )
    return Response.success(msg="添加成员成功", data=_to_item(view))


@router.post(
    path="/{membership_id}/role",
    response_model=Response[MemberItem],
    summary="变更成员角色",
    description="将成员设置为管理员或普通成员(仅 owner/admin；不能变更所有者)",
)
async def change_member_role(
        membership_id: str,
        request: ChangeRoleRequest,
        current_user: CurrentUser = Depends(_require_org_admin),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[MemberItem]:
    """变更成员角色"""
    view = await membership_service.change_role(
        tenant_id=current_user.tenant_id,
        membership_id=membership_id,
        role=request.role,
    )
    return Response.success(msg="变更成员角色成功", data=_to_item(view))


@router.post(
    path="/{membership_id}/delete",
    response_model=Response[dict],
    summary="移除成员",
    description="将成员移出当前组织(仅 owner/admin；不能移除所有者)",
)
async def remove_member(
        membership_id: str,
        current_user: CurrentUser = Depends(_require_org_admin),
        membership_service: MembershipService = Depends(get_membership_service),
) -> Response[dict]:
    """移除成员"""
    await membership_service.remove_member(
        tenant_id=current_user.tenant_id,
        membership_id=membership_id,
    )
    return Response.success(msg="移除成员成功")
