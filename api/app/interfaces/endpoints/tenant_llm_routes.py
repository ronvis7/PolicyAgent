"""租户级 LLM 配置路由：组织 owner/admin 可配置本组织自己的 LLM(BYO key)。

与平台级配置(MCP/A2A/Agent，见 app_config_routes，仅平台管理员)分离：LLM 密钥
按租户隔离，未配置时运行时回落平台默认配置(config.yaml)。
"""

import logging

from fastapi import APIRouter, Depends

from app.application.services.tenant_settings_service import TenantSettingsService
from app.domain.models.app_config import EmbedConfig, LLMConfig
from app.domain.models.membership import MembershipRole
from app.interfaces.auth_dependencies import CurrentUser, get_current_user, require_role
from app.interfaces.schemas.app_config import (
    PublicEmbedConfig,
    PublicLLMConfig,
    UpdateEmbedConfigRequest,
)
from app.interfaces.schemas.base import Response
from app.interfaces.service_dependencies import get_tenant_settings_service
from core.config import get_settings

logger = logging.getLogger(__name__)

# 组织 owner/admin 均可管理本组织 LLM 配置
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)

router = APIRouter(prefix="/app-config", tags=["设置模块"])

# 占位密钥不视为"已配置"
_PLACEHOLDER_API_KEYS = {"local-placeholder", "sk-your_deepseek_api_key_here"}


def _to_public_llm_config(llm_config: LLMConfig, is_custom: bool) -> PublicLLMConfig:
    """将 LLM 配置转换为不含密钥明文的安全响应"""
    api_key = llm_config.api_key.strip().lower()
    return PublicLLMConfig(
        base_url=llm_config.base_url,
        model_name=llm_config.model_name,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        api_key_configured=bool(api_key) and api_key not in _PLACEHOLDER_API_KEYS,
        is_custom=is_custom,
    )


@router.get(
    path="/llm",
    response_model=Response[PublicLLMConfig],
    summary="获取当前组织生效的LLM配置",
    description="返回当前组织生效的LLM配置(组织自定义优先，否则为平台默认)；is_custom标识是否为组织自定义",
)
async def get_llm_config(
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicLLMConfig]:
    """获取当前组织生效的LLM配置"""
    llm_config, is_custom = await tenant_settings_service.resolve_llm_config(current_user.tenant_id)
    return Response.success(data=_to_public_llm_config(llm_config, is_custom))


@router.post(
    path="/llm",
    response_model=Response[PublicLLMConfig],
    summary="更新当前组织的LLM配置",
    description="更新当前组织自己的LLM配置；api_key为空表示不修改密钥(沿用已有或平台默认)",
)
async def update_llm_config(
        new_llm_config: LLMConfig,
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicLLMConfig]:
    """更新当前组织的LLM配置"""
    updated_llm_config, is_custom = await tenant_settings_service.update_llm_config(
        current_user.tenant_id, new_llm_config
    )
    return Response.success(
        msg="更新LLM信息配置成功",
        data=_to_public_llm_config(updated_llm_config, is_custom),
    )


def _to_public_embed_config(embed_config: EmbedConfig, is_custom: bool) -> PublicEmbedConfig:
    """将 Embedding 配置转换为不含密钥明文的安全响应。

    base_url/model/dimension 为平台锁定值(只读)。api_key_configured：组织自定义则必有 key；
    否则取决于平台 .env 是否配置了 embed key。
    """
    configured = is_custom or bool(get_settings().embed_api_key.strip())
    return PublicEmbedConfig(
        base_url=embed_config.base_url,
        model_name=embed_config.model_name,
        dimension=embed_config.dimension,
        api_key_configured=configured,
        is_custom=is_custom,
    )


@router.get(
    path="/embedding",
    response_model=Response[PublicEmbedConfig],
    summary="获取当前组织生效的Embedding配置",
    description="返回当前组织生效的Embedding配置(双轨私有侧)；base_url/model/dimension为平台锁定值，仅api_key可组织自定义",
)
async def get_embed_config(
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicEmbedConfig]:
    """获取当前组织生效的Embedding配置"""
    embed_config, is_custom = await tenant_settings_service.resolve_embed_config(current_user.tenant_id)
    return Response.success(data=_to_public_embed_config(embed_config, is_custom))


@router.post(
    path="/embedding",
    response_model=Response[PublicEmbedConfig],
    summary="更新当前组织的Embedding密钥",
    description="组织自配Embedding api_key(BYO，私有库向量化计费归属组织)；api_key为空表示不修改。模型与维度锁平台，不可改",
)
async def update_embed_config(
        request: UpdateEmbedConfigRequest,
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicEmbedConfig]:
    """更新当前组织的Embedding密钥"""
    embed_config, is_custom = await tenant_settings_service.update_embed_config(
        current_user.tenant_id, request.api_key
    )
    return Response.success(
        msg="更新Embedding配置成功",
        data=_to_public_embed_config(embed_config, is_custom),
    )
