"""公开政策库路由：全局共享层，所有登录用户可分页浏览 + 查看详情。

抓取入库可由 owner/admin 经 POST /policies/ingest 后台触发(API 进程内执行，复用其
DB/embedding 连接，免去主机直连远程库的隧道/端口问题)；也可用脚本 scripts/crawl_wnd_policies.py。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.application.errors.exceptions import BadRequestError
from app.application.services.feed_service import FeedService
from app.application.services.policy_ingest_service import PolicyIngestService
from app.application.services.policy_match_service import PolicyMatchService
from app.application.services.policy_service import PolicyService
from app.domain.models.membership import MembershipRole
from app.infrastructure.external.crawler.registry import list_sources
from app.interfaces.auth_dependencies import CurrentUser, get_current_user, require_role
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.policy import (
    PolicyDetailResponse,
    PolicyListItem,
    PolicyListResponse,
    PolicyMatchItem,
    PolicyMatchResponse,
    PolicySourceItem,
    PolicySourceListResponse,
)
from app.interfaces.service_dependencies import (
    get_feed_service,
    get_policy_ingest_service,
    get_policy_match_service,
    get_policy_service,
)

logger = logging.getLogger(__name__)

# 抓取入库限组织 owner/admin（公开库为全局共享，写入应受控）
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)

router = APIRouter(prefix="/policies", tags=["公开政策库"])


@router.post(
    path="/ingest",
    response_model=Response[dict],
    summary="后台抓取无锡新吴区公开政策入库",
    description=(
        "在 API 进程内后台抓取「政策文件」栏目并结构化 upsert + 向量双写(不阻塞请求，立即返回)。"
        "复用 API 自身的 DB/embedding 连接。仅组织 owner/admin 可触发。完成后刷新列表查看。"
    ),
)
async def ingest_policies(
        background_tasks: BackgroundTasks,
        source: str = Query("wnd", description="政策来源 key(见 GET /policies/sources)"),
        max_pages: int = Query(3, ge=1, le=20, description="抓取的列表页数(每页约20条)"),
        current_user: CurrentUser = Depends(_require_org_admin),
        service: PolicyIngestService = Depends(get_policy_ingest_service),
        feed_service: FeedService = Depends(get_feed_service),
) -> Response[dict]:
    """后台触发指定来源的公开政策抓取入库；入库后顺带重算当前租户工作台 Feed(④ 触发 a)"""
    valid_keys = {s.key for s in list_sources()}
    if source not in valid_keys:
        raise BadRequestError(f"未知的政策来源：{source}")
    # BackgroundTasks 按加入顺序串行执行：先抓取入库，再据新政策重算当前租户 Feed
    background_tasks.add_task(service.ingest, source, max_pages)
    background_tasks.add_task(feed_service.recompute_for_tenant, current_user.tenant_id)
    logger.info(
        "已排入后台政策抓取+Feed重算任务: source=%s max_pages=%s tenant=%s",
        source, max_pages, current_user.tenant_id,
    )
    return Response.success(
        msg=f"已开始后台抓取最新政策(最多 {max_pages} 页)，约 1-2 分钟后刷新列表/工作台查看",
        data={"source": source, "max_pages": max_pages},
    )


@router.get(
    path="/sources",
    response_model=Response[PolicySourceListResponse],
    summary="列出可抓取的政策来源(地区/门户)",
    description="返回已登记的公开政策来源(key/名称/地区)，供前端来源选择器与按地区筛选。所有登录用户可访问。",
)
async def list_policy_sources(
        _current_user: CurrentUser = Depends(get_current_user),
        service: PolicyService = Depends(get_policy_service),
) -> Response[PolicySourceListResponse]:
    """列出可抓取的政策来源(含官网链接 + 收录条数 + 最近抓取时间)"""
    sources = await service.list_sources_with_stats()
    items = [
        PolicySourceItem(
            key=s.key, name=s.name, region=s.region, home_url=s.home_url,
            policy_count=s.policy_count, last_crawled_at=s.last_crawled_at,
        )
        for s in sources
    ]
    return Response.success(data=PolicySourceListResponse(items=items))


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
    path="/match",
    response_model=Response[PolicyMatchResponse],
    summary="企业档案匹配公开政策(③匹配)",
    description=(
        "按当前登录租户的企业档案，结合结构化命中(关键词/技术域/资质/行业)与语义召回"
        "(档案画像检索公开政策库)，经 RRF 融合返回可申报政策候选(带推荐理由)。"
        "即时计算，档案为空时返回空列表。所有登录用户可访问，结果限当前租户档案。"
    ),
)
async def match_policies(
        top_k: int = Query(20, ge=1, le=50, description="返回候选数(1-50)"),
        current_user: CurrentUser = Depends(get_current_user),
        service: PolicyMatchService = Depends(get_policy_match_service),
) -> Response[PolicyMatchResponse]:
    """按当前租户企业档案匹配公开政策候选"""
    matches = await service.match_for_tenant(current_user.tenant_id, top_k=top_k)
    return Response.success(data=PolicyMatchResponse(
        items=[PolicyMatchItem.from_domain(m) for m in matches],
        total=len(matches),
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
