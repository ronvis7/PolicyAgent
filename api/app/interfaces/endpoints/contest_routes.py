from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.application.services.contest_service import ContestService
from app.application.services.policy_ingest_service import PolicyIngestService
from app.domain.models.contest import ContestSource
from app.domain.models.membership import MembershipRole
from app.interfaces.auth_dependencies import CurrentUser, get_current_user, require_platform_admin, require_role
from app.interfaces.schemas.base import Response
from app.interfaces.schemas.contest import (
    ContestDetailResponse, ContestItemResponse, ContestListResponse, ContestSourceListResponse,
    ContestSourcePatchRequest, ContestSourceRequest, ContestSourceResponse,
    ContestSubscriptionListResponse, ContestSubscriptionPatchRequest, ContestSubscriptionRequest,
    ContestSubscriptionResponse,
)
from app.interfaces.service_dependencies import get_contest_service, get_policy_ingest_service

router = APIRouter(tags=["赛事中心"])
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)


@router.get("/contests", response_model=Response[ContestListResponse])
async def list_contests(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), origin: str = Query(""),
    region: str = Query(""), source: str = Query(""), keyword: str = Query(""), active_only: bool = Query(True),
    _user: CurrentUser = Depends(get_current_user), service: ContestService = Depends(get_contest_service),
) -> Response[ContestListResponse]:
    items, total = await service.list_contests(page=page, page_size=page_size, origin=origin, region=region,
                                               source=source, keyword=keyword, active_only=active_only)
    return Response.success(data=ContestListResponse(items=[ContestItemResponse.from_domain(i) for i in items], total=total, page=page, page_size=page_size))


@router.get("/contests/{contest_id}", response_model=Response[ContestDetailResponse])
async def get_contest(contest_id: str, _user: CurrentUser = Depends(get_current_user), service: ContestService = Depends(get_contest_service)) -> Response[ContestDetailResponse]:
    return Response.success(data=ContestDetailResponse.from_domain(await service.get_contest(contest_id)))


@router.get("/contest-sources", response_model=Response[ContestSourceListResponse])
async def list_sources(_user: CurrentUser = Depends(get_current_user), service: ContestService = Depends(get_contest_service)) -> Response[ContestSourceListResponse]:
    return Response.success(data=ContestSourceListResponse(items=[ContestSourceResponse.from_domain(s) for s in await service.list_sources()]))


@router.get("/contest-subscriptions", response_model=Response[ContestSubscriptionListResponse])
async def list_subscriptions(user: CurrentUser = Depends(_require_org_admin), service: ContestService = Depends(get_contest_service)) -> Response[ContestSubscriptionListResponse]:
    return Response.success(data=ContestSubscriptionListResponse(items=[ContestSubscriptionResponse.from_domain(s) for s in await service.list_subscriptions(user.tenant_id)]))


@router.post("/contest-subscriptions", response_model=Response[ContestSubscriptionResponse])
async def create_subscription(request: ContestSubscriptionRequest, user: CurrentUser = Depends(_require_org_admin), service: ContestService = Depends(get_contest_service)) -> Response[ContestSubscriptionResponse]:
    return Response.success(data=ContestSubscriptionResponse.from_domain(await service.create_subscription(user.tenant_id, request.keyword)), msg="关键词订阅已创建")


@router.patch("/contest-subscriptions/{subscription_id}", response_model=Response[ContestSubscriptionResponse])
async def update_subscription(subscription_id: str, request: ContestSubscriptionPatchRequest, user: CurrentUser = Depends(_require_org_admin), service: ContestService = Depends(get_contest_service)) -> Response[ContestSubscriptionResponse]:
    return Response.success(data=ContestSubscriptionResponse.from_domain(await service.update_subscription(user.tenant_id, subscription_id, request.enabled)))


@router.delete("/contest-subscriptions/{subscription_id}", response_model=Response[dict])
async def delete_subscription(subscription_id: str, user: CurrentUser = Depends(_require_org_admin), service: ContestService = Depends(get_contest_service)) -> Response[dict]:
    await service.delete_subscription(user.tenant_id, subscription_id)
    return Response.success(data={})


platform_router = APIRouter(prefix="/platform/contest-sources", tags=["平台赛事来源"], dependencies=[Depends(require_platform_admin)])


@platform_router.post("", response_model=Response[ContestSourceResponse])
async def create_source(request: ContestSourceRequest, service: ContestService = Depends(get_contest_service)) -> Response[ContestSourceResponse]:
    source = ContestSource(**request.model_dump())
    return Response.success(data=ContestSourceResponse.from_domain(await service.save_source(source)))


@platform_router.patch("/{source_id}", response_model=Response[ContestSourceResponse])
async def update_source(source_id: str, request: ContestSourcePatchRequest, service: ContestService = Depends(get_contest_service)) -> Response[ContestSourceResponse]:
    changes = {key: value for key, value in request.model_dump().items() if value is not None}
    return Response.success(data=ContestSourceResponse.from_domain(await service.update_source(source_id, **changes)))


@platform_router.delete("/{source_id}", response_model=Response[dict])
async def delete_source(source_id: str, service: ContestService = Depends(get_contest_service)) -> Response[dict]:
    await service.delete_source(source_id)
    return Response.success(data={})


@platform_router.post("/{source_id}/preflight", response_model=Response[dict])
async def preflight_source(source_id: str, service: ContestService = Depends(get_contest_service)) -> Response[dict]:
    return Response.success(data=await service.preflight_source(source_id))


@platform_router.post("/{source_id}/ingest", response_model=Response[dict])
async def ingest_source(source_id: str, tasks: BackgroundTasks, service: ContestService = Depends(get_contest_service), ingest: PolicyIngestService = Depends(get_policy_ingest_service)) -> Response[dict]:
    tasks.add_task(service.ingest_source, source_id, ingest)
    return Response.success(data={"source_id": source_id}, msg="官方赛事来源已开始后台抓取")
