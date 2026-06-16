"""资质申报机会路由（主线⑥ 能力①）：按当前租户档案匹配资质目录、取详情。

所有登录用户，限当前租户上下文。资质也会通过 ④ 工作台 Feed 以 type=qualification 呈现；
本路由提供"可申报资质"专项列表与详情(含风险纪律免责声明)。
"""

import logging

from fastapi import APIRouter, Depends

from app.application.errors.exceptions import NotFoundError
from app.application.services.qualification_service import QualificationService
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.qualification import (
    QualificationDetailResponse,
    QualificationGapResponse,
    QualificationMatchListResponse,
    QualificationMatchResponse,
)
from app.interfaces.service_dependencies import get_qualification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qualifications", tags=["资质申报机会"])


@router.get(
    path="",
    response_model=Response[QualificationMatchListResponse],
    summary="可申报资质（按当前租户档案匹配）",
    description=(
        "按当前租户企业档案匹配资质目录：排除地区不适用项，按'可申报优先、匹配分倒序'返回，"
        "标注'可申报/接近可申报(差N项)'与差距雏形。无档案返回空列表。"
    ),
)
async def list_qualification_matches(
        current_user: CurrentUser = Depends(get_current_user),
        service: QualificationService = Depends(get_qualification_service),
) -> Response[QualificationMatchListResponse]:
    """可申报资质列表"""
    matches = await service.match_for_tenant(current_user.tenant_id)
    items = [QualificationMatchResponse.from_domain(m) for m in matches]
    return Response.success(data=QualificationMatchListResponse(
        items=items,
        total=len(items),
        eligible_count=sum(1 for m in matches if m.eligible),
    ))


@router.get(
    path="/{key}/gap",
    response_model=Response[QualificationGapResponse],
    summary="资质条件差距分析（能力②）",
    description=(
        "按当前租户档案对指定资质做条件差距分析：可结构化核验的硬条件逐条给出 达标/不达标/待确认，"
        "无结构化对应的条件归入'需人工/材料确认'。门槛为结构性概要，务必连同免责声明展示。"
    ),
)
async def get_qualification_gap(
        key: str,
        current_user: CurrentUser = Depends(get_current_user),
        service: QualificationService = Depends(get_qualification_service),
) -> Response[QualificationGapResponse]:
    """资质条件差距分析"""
    report = await service.analyze_gap_for_tenant(current_user.tenant_id, key)
    if report is None:
        raise NotFoundError(msg="资质不存在")
    return Response.success(data=QualificationGapResponse.from_domain(report))


@router.get(
    path="/{key}",
    response_model=Response[QualificationDetailResponse],
    summary="资质详情",
    description="按 key 返回资质详情（核心条件/材料/时间/政策依据/价值）。务必连同免责声明与末次核对日期展示。",
)
async def get_qualification_detail(
        key: str,
        current_user: CurrentUser = Depends(get_current_user),
        service: QualificationService = Depends(get_qualification_service),
) -> Response[QualificationDetailResponse]:
    """资质详情"""
    qual = service.get_by_key(key)
    if qual is None:
        raise NotFoundError(msg="资质不存在")
    return Response.success(data=QualificationDetailResponse.from_domain(qual))
