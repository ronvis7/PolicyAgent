"""主动情报简报路由：读取/即时生成当前组织的情报简报。

Agent 会定时在后台为已建档企业自主生成"带理由的优先级机会简报"；此处让用户随时查看
最新一份，或点"立即生成"按需触发。所有操作限当前登录租户。
"""

import logging

from fastapi import APIRouter, Depends

from app.application.services.briefing_service import BriefingService
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.briefing import BriefingResponse
from app.interfaces.service_dependencies import get_briefing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefings", tags=["主动情报"])


@router.get(
    path="/latest",
    response_model=Response[BriefingResponse],
    summary="获取当前组织最新的情报简报",
    description="返回 Agent 最近为当前企业生成的主动情报简报；从未生成则 has_briefing=false。",
)
async def get_latest_briefing(
        current_user: CurrentUser = Depends(get_current_user),
        service: BriefingService = Depends(get_briefing_service),
) -> Response[BriefingResponse]:
    """获取最新情报简报"""
    briefing = await service.get_latest(current_user.tenant_id)
    return Response.success(data=BriefingResponse.from_domain(briefing))


@router.post(
    path="/generate",
    response_model=Response[BriefingResponse],
    summary="立即为当前组织生成情报简报",
    description="基于当前企业档案与已匹配机会即时生成一份情报简报并保存（LLM 优先，失败回退兜底）。",
)
async def generate_briefing(
        current_user: CurrentUser = Depends(get_current_user),
        service: BriefingService = Depends(get_briefing_service),
) -> Response[BriefingResponse]:
    """立即生成情报简报"""
    briefing = await service.generate(current_user.tenant_id)
    return Response.success(msg="情报简报已生成", data=BriefingResponse.from_domain(briefing))
