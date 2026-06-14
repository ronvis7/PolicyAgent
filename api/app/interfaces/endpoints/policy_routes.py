"""公开政策库路由：全局共享层，所有登录用户可分页浏览 + 查看详情。

入库/爬取由后台脚本(scripts/crawl_wnd_policies.py)经 PolicyIngestService 完成，不在此暴露。
"""

import logging

from fastapi import APIRouter, Depends, Query

from app.application.services.policy_service import PolicyService
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.policy import (
    PolicyDetailResponse,
    PolicyListItem,
    PolicyListResponse,
)
from app.interfaces.service_dependencies import get_policy_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["公开政策库"])


@router.get(
    path="",
    response_model=Response[PolicyListResponse],
    summary="分页浏览公开政策库",
    description="按发文日期倒序分页返回公开政策(全局共享)。支持按地区/发文机构/标题关键词筛选。所有登录用户可访问。",
)
async def list_policies(
        page: int = Query(1, ge=1, description="页码(从1开始)"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数(1-100)"),
        region: str = Query("", description="按适用地区筛选(模糊)"),
        issuer: str = Query("", description="按发文机构筛选(模糊)"),
        keyword: str = Query("", description="按标题关键词筛选(模糊)"),
        _current_user: CurrentUser = Depends(get_current_user),
        service: PolicyService = Depends(get_policy_service),
) -> Response[PolicyListResponse]:
    """分页浏览公开政策库"""
    items, total = await service.list_policies(
        page=page, page_size=page_size, region=region, issuer=issuer, keyword=keyword,
    )
    return Response.success(data=PolicyListResponse(
        items=[PolicyListItem.from_domain(p) for p in items],
        total=total, page=page, page_size=page_size,
    ))


@router.get(
    path="/{policy_id}",
    response_model=Response[PolicyDetailResponse],
    summary="查看政策详情",
    description="返回单篇政策的完整信息(含正文)。所有登录用户可访问。",
)
async def get_policy(
        policy_id: str,
        _current_user: CurrentUser = Depends(get_current_user),
        service: PolicyService = Depends(get_policy_service),
) -> Response[PolicyDetailResponse]:
    """查看政策详情"""
    policy = await service.get_policy(policy_id)
    return Response.success(data=PolicyDetailResponse.from_domain(policy))
