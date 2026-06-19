"""企业档案路由：以企业为主体的主动服务链路源头。

每个租户一条档案。查看对租户内所有成员开放；编辑限组织 owner/admin。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from app.application.services.enterprise_profile_service import EnterpriseProfileService
from app.application.services.feed_service import FeedService
from app.domain.models.membership import MembershipRole
from app.domain.services.keyword_extractor import suggest_keywords
from app.interfaces.auth_dependencies import CurrentUser, get_current_user, require_role
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.enterprise_profile import (
    EnterpriseProfileResponse,
    KeywordSuggestRequest,
    KeywordSuggestResponse,
    UpdateEnterpriseProfileRequest,
)
from app.interfaces.service_dependencies import (
    get_enterprise_profile_service,
    get_feed_service,
)

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
        background_tasks: BackgroundTasks,
        current_user: CurrentUser = Depends(_require_org_admin),
        service: EnterpriseProfileService = Depends(get_enterprise_profile_service),
        feed_service: FeedService = Depends(get_feed_service),
) -> Response[EnterpriseProfileResponse]:
    """更新当前组织的企业档案；保存后重算当前租户工作台 Feed(④ 触发 b)"""
    profile = await service.update_profile(
        current_user.tenant_id, request.to_domain(current_user.tenant_id)
    )
    # 档案变了，可申报政策也会变：后台重算当前租户 Feed(④ 触发 b，不阻塞响应)
    background_tasks.add_task(feed_service.recompute_for_tenant, current_user.tenant_id)
    return Response.success(
        msg="更新企业档案成功",
        data=EnterpriseProfileResponse.from_domain(profile),
    )


@router.post(
    path="/keyword-suggestions",
    response_model=Response[KeywordSuggestResponse],
    summary="从自述文本智能提取候选关键词",
    description=(
        "对主营业务/行业等自述文本做中文关键词抽取，返回候选关键词(已过滤停用词与已填项)，"
        "供档案编辑时一键补全。建议词取自企业自身描述，对 ③ 结构化匹配命中最有帮助。"
    ),
)
async def suggest_profile_keywords(
        request: KeywordSuggestRequest,
        current_user: CurrentUser = Depends(get_current_user),
) -> Response[KeywordSuggestResponse]:
    """关键词智能提取(无状态纯计算，所有登录用户可用)"""
    suggestions = suggest_keywords(request.text, exclude=request.exclude)
    return Response.success(data=KeywordSuggestResponse(suggestions=suggestions))
