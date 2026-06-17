"""工作台 Feed 路由（主线④）：物化的政策/机会信息流，所有登录用户，限当前租户。

③ 解决"算得出"，④ 解决"系统替你盯、有新的顶上来"。Feed 由触发(抓取后/改档案后/手动)
重算物化；本路由提供浏览、未读计数、状态流转与手动重算。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.application.errors.exceptions import BadRequestError
from app.application.services.feed_service import FeedService
from app.domain.models.feed_item import FeedStatus
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.feed import (
    ExpiringListResponse,
    FeedItemResponse,
    FeedListResponse,
    RecomputeResponse,
    SetFeedStatusRequest,
    UnreadCountResponse,
)

# 临期提醒默认窗口(天)：覆盖常见"提前两周准备申报"的节奏
_DEFAULT_EXPIRING_WINDOW_DAYS = 14
from app.interfaces.service_dependencies import get_feed_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["工作台 Feed"])


def _parse_status(status: str) -> Optional[FeedStatus]:
    """把查询字符串解析为状态枚举(空串表示不过滤)，非法值报 400。"""
    if not status:
        return None
    try:
        return FeedStatus(status)
    except ValueError:
        raise BadRequestError(msg=f"无效的 status：{status}")


@router.get(
    path="",
    response_model=Response[FeedListResponse],
    summary="分页浏览工作台 Feed",
    description="按创建时间倒序分页返回当前租户的政策/机会信息流。可按状态(unread/read/applied/ignored)筛选。",
)
async def list_feed(
        status: str = Query("", description="按状态筛选(unread/read/applied/ignored)，空为全部"),
        page: int = Query(1, ge=1, description="页码(从1开始)"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数(1-100)"),
        current_user: CurrentUser = Depends(get_current_user),
        service: FeedService = Depends(get_feed_service),
) -> Response[FeedListResponse]:
    """分页浏览当前租户工作台 Feed"""
    items, total = await service.list_feed(
        current_user.tenant_id, status=_parse_status(status), page=page, page_size=page_size,
    )
    return Response.success(data=FeedListResponse(
        items=[FeedItemResponse.from_domain(i) for i in items],
        total=total, page=page, page_size=page_size,
    ))


@router.get(
    path="/unread-count",
    response_model=Response[UnreadCountResponse],
    summary="当前租户未读条数",
    description="返回当前租户工作台未读条目数，用于左栏红点/计数。",
)
async def get_unread_count(
        current_user: CurrentUser = Depends(get_current_user),
        service: FeedService = Depends(get_feed_service),
) -> Response[UnreadCountResponse]:
    """获取未读计数"""
    count = await service.unread_count(current_user.tenant_id)
    return Response.success(data=UnreadCountResponse(count=count))


@router.get(
    path="/expiring",
    response_model=Response[ExpiringListResponse],
    summary="临期申报机会",
    description=(
        "返回当前租户未来 within_days 天内申报截止且未忽略的机会(按截止日期升序，最紧的在前)。"
        "仅含从政策正文抽取到明确截止日期的条目；截止日期以政策原文为准、供参考核对。"
    ),
)
async def list_expiring(
        within_days: int = Query(
            _DEFAULT_EXPIRING_WINDOW_DAYS, ge=1, le=180, description="临期窗口天数(1-180)",
        ),
        current_user: CurrentUser = Depends(get_current_user),
        service: FeedService = Depends(get_feed_service),
) -> Response[ExpiringListResponse]:
    """临期申报机会(主线⑤)"""
    items = await service.list_expiring(current_user.tenant_id, within_days)
    return Response.success(data=ExpiringListResponse(
        items=[FeedItemResponse.from_domain(i) for i in items],
        count=len(items), within_days=within_days,
    ))


@router.post(
    path="/recompute",
    response_model=Response[RecomputeResponse],
    summary="手动重算当前租户 Feed",
    description=(
        "按当前租户企业档案重算可申报政策并物化：新增条目记未读、已存在的更新快照但保留用户状态、"
        "跌出候选的旧条目保留。用于兜住跨租户(别人抓的新政策本租户点一下即可拉到)。"
    ),
)
async def recompute_feed(
        current_user: CurrentUser = Depends(get_current_user),
        service: FeedService = Depends(get_feed_service),
) -> Response[RecomputeResponse]:
    """手动重算当前租户 Feed"""
    result = await service.recompute_for_tenant(current_user.tenant_id)
    return Response.success(
        msg=f"重算完成：新增 {result['new']} 条，更新 {result['updated']} 条",
        data=RecomputeResponse(**result),
    )


@router.post(
    path="/mark-read",
    response_model=Response[dict],
    summary="全部标记已读",
    description="把当前租户所有未读条目置为已读(打开工作台时清红点)。",
)
async def mark_all_read(
        current_user: CurrentUser = Depends(get_current_user),
        service: FeedService = Depends(get_feed_service),
) -> Response[dict]:
    """全部标记已读"""
    affected = await service.mark_all_read(current_user.tenant_id)
    return Response.success(msg=f"已标记 {affected} 条为已读", data={"affected": affected})


@router.post(
    path="/{item_id}/status",
    response_model=Response[FeedItemResponse],
    summary="更新单条 Feed 状态",
    description="更新某条 Feed 状态为 read/applied/ignored(校验归属当前租户)。",
)
async def set_feed_status(
        item_id: str,
        request: SetFeedStatusRequest,
        current_user: CurrentUser = Depends(get_current_user),
        service: FeedService = Depends(get_feed_service),
) -> Response[FeedItemResponse]:
    """更新单条 Feed 状态"""
    item = await service.set_status(
        current_user.tenant_id, item_id, FeedStatus(request.status),
    )
    return Response.success(msg="状态已更新", data=FeedItemResponse.from_domain(item))
