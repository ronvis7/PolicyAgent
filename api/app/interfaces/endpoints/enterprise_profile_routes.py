"""企业档案路由：以企业为主体的主动服务链路源头。

每个租户一条档案。查看对租户内所有成员开放；编辑限组织 owner/admin。
"""

import logging

from fastapi import APIRouter, Depends

from app.application.services.enterprise_profile_service import EnterpriseProfileService
from app.domain.models.membership import MembershipRole
from app.interfaces.auth_dependencies import CurrentUser, get_current_user, require_role
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.enterprise_profile import (
    EnterpriseProfileResponse,
    UpdateEnterpriseProfileRequest,
)
from app.interfaces.service_dependencies import get_enterprise_profile_service

logger = logging.getLogger(__name__)

# 组织 owner/admin 可编辑本组织档案
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)

router = APIRouter(prefix="/enterprise-profile", tags=["企业档案"])


@router.get(
    path="",
    response_model=Response[EnterpriseProfileResponse],
    summary="获取当前组织的企业档案",
    description="返回当前组织的企业档案；从未填写过则返回带默认地区的空档案。租户内成员均可查看。",
)
async def get_enterprise_profile(
        current_user: CurrentUser = Depends(get_current_user),
        service: EnterpriseProfileService = Depends(get_enterprise_profile_service),
) -> Response[EnterpriseProfileResponse]:
    """获取当前组织的企业档案"""
    profile = await service.get_profile(current_user.tenant_id)
    return Response.success(data=EnterpriseProfileResponse.from_domain(profile))


@router.put(
    path="",
    response_model=Response[EnterpriseProfileResponse],
    summary="更新当前组织的企业档案",
    description="整体覆盖当前组织的企业档案(不存在则创建)。仅组织 owner/admin 可操作。",
)
async def update_enterprise_profile(
        request: UpdateEnterpriseProfileRequest,
        current_user: CurrentUser = Depends(_require_org_admin),
        service: EnterpriseProfileService = Depends(get_enterprise_profile_service),
) -> Response[EnterpriseProfileResponse]:
    """更新当前组织的企业档案"""
    profile = await service.update_profile(
        current_user.tenant_id, request.to_domain(current_user.tenant_id)
    )
    return Response.success(
        msg="更新企业档案成功",
        data=EnterpriseProfileResponse.from_domain(profile),
    )
