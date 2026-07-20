"""租户级赛事搜索配置：组织 owner/admin 自助配置百度千帆 API Key。"""

from fastapi import APIRouter, Depends

from app.application.services.tenant_settings_service import TenantSettingsService
from app.domain.models.membership import MembershipRole
from app.interfaces.auth_dependencies import CurrentUser, require_role
from app.interfaces.schemas.app_config import (
    PublicContestSearchConfig,
    UpdateContestSearchConfigRequest,
)
from app.interfaces.schemas.base import Response
from app.interfaces.service_dependencies import get_tenant_settings_service
from core.config import get_settings

router = APIRouter(prefix="/app-config", tags=["设置模块"])
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)


def _to_public(is_custom: bool) -> PublicContestSearchConfig:
    settings = get_settings()
    platform_provider = settings.contest_search_provider.strip().lower()
    using_baidu = is_custom or (
        platform_provider in {"auto", "baidu"} and bool(settings.baidu_search_api_key.strip())
    )
    return PublicContestSearchConfig(
        provider="baidu" if using_baidu else "bing",
        api_key_configured=is_custom or bool(settings.baidu_search_api_key.strip()),
        is_custom=is_custom,
        fallback_enabled=settings.contest_search_fallback_enabled,
    )


@router.get(
    "/contest-search",
    response_model=Response[PublicContestSearchConfig],
    summary="获取当前组织赛事搜索配置",
)
async def get_contest_search_config(
        current_user: CurrentUser = Depends(_require_org_admin),
        service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicContestSearchConfig]:
    config = await service.get_contest_search_config(current_user.tenant_id)
    return Response.success(data=_to_public(config is not None))


@router.post(
    "/contest-search",
    response_model=Response[PublicContestSearchConfig],
    summary="更新当前组织百度赛事搜索密钥",
)
async def update_contest_search_config(
        request: UpdateContestSearchConfigRequest,
        current_user: CurrentUser = Depends(_require_org_admin),
        service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicContestSearchConfig]:
    config = await service.update_contest_search_config(current_user.tenant_id, request.api_key)
    return Response.success(msg="赛事搜索配置保存成功", data=_to_public(config is not None))
