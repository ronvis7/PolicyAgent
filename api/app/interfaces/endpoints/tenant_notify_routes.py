"""租户级飞书推送配置路由：组织 owner/admin 在设置页配置本组织的飞书群机器人 webhook。

配置存 tenant_settings.feishu_config(见迁移 e2f3a4b5c6d7)；新赛事入库时按租户扇出推送、
按各租户"参赛关注地区"过滤(见 feishu_webhook.make_tenant_contest_push_hook)。
webhook URL 即推送凭据，只脱敏回显；secret 只回显是否已配置。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends

from app.application.errors.exceptions import BadRequestError
from app.application.services.tenant_settings_service import TenantSettingsService
from app.domain.models.membership import MembershipRole
from app.domain.models.tenant_settings import FeishuNotifyConfig
from app.infrastructure.external.notify.feishu_webhook import (
    FeishuWebhookNotifier,
    build_test_message,
    mask_webhook_url,
)
from app.interfaces.auth_dependencies import CurrentUser, require_role
from app.interfaces.schemas.app_config import PublicFeishuConfig, UpdateFeishuConfigRequest
from app.interfaces.schemas.base import Response
from app.interfaces.service_dependencies import get_tenant_settings_service

logger = logging.getLogger(__name__)

# 与租户级 LLM 配置同门禁：组织 owner/admin 可管理本组织推送配置
_require_org_admin = require_role(MembershipRole.OWNER.value, MembershipRole.ADMIN.value)

router = APIRouter(prefix="/app-config", tags=["设置模块"])


def _to_public(config: Optional[FeishuNotifyConfig]) -> PublicFeishuConfig:
    """转换为不含凭据明文的安全响应"""
    if config is None or not config.webhook_url.strip():
        return PublicFeishuConfig()
    return PublicFeishuConfig(
        configured=True,
        webhook_url_masked=mask_webhook_url(config.webhook_url),
        secret_configured=bool(config.secret.strip()),
    )


@router.get(
    path="/feishu",
    response_model=Response[PublicFeishuConfig],
    summary="获取当前组织的飞书推送配置",
    description="返回当前组织的飞书群机器人 webhook 配置(脱敏)；未配置表示不推送新赛事",
)
async def get_feishu_config(
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicFeishuConfig]:
    """获取当前组织的飞书推送配置"""
    config = await tenant_settings_service.get_feishu_config(current_user.tenant_id)
    return Response.success(data=_to_public(config))


@router.post(
    path="/feishu",
    response_model=Response[PublicFeishuConfig],
    summary="更新当前组织的飞书推送配置",
    description="配置本组织飞书群机器人 webhook(新赛事将推送到该群)；secret 为空表示不修改已有签名密钥",
)
async def update_feishu_config(
        request: UpdateFeishuConfigRequest,
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicFeishuConfig]:
    """更新当前组织的飞书推送配置"""
    config = await tenant_settings_service.update_feishu_config(
        current_user.tenant_id, request.webhook_url, request.secret,
    )
    return Response.success(msg="飞书推送配置保存成功", data=_to_public(config))


@router.post(
    path="/feishu/delete",
    response_model=Response[PublicFeishuConfig],
    summary="清除当前组织的飞书推送配置",
    description="停用本组织的新赛事飞书推送(清除已保存的 webhook 与签名密钥)",
)
async def clear_feishu_config(
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicFeishuConfig]:
    """清除当前组织的飞书推送配置"""
    await tenant_settings_service.clear_feishu_config(current_user.tenant_id)
    return Response.success(msg="已停用飞书推送", data=PublicFeishuConfig())


@router.post(
    path="/feishu/test",
    response_model=Response[PublicFeishuConfig],
    summary="发送飞书测试消息",
    description="用已保存的配置向组织飞书群发送一条测试消息，验证 webhook 与签名是否正确",
)
async def test_feishu_push(
        current_user: CurrentUser = Depends(_require_org_admin),
        tenant_settings_service: TenantSettingsService = Depends(get_tenant_settings_service),
) -> Response[PublicFeishuConfig]:
    """向组织飞书群发送测试消息(用已保存的配置)"""
    config = await tenant_settings_service.get_feishu_config(current_user.tenant_id)
    public = _to_public(config)  # "已配置"判定与 GET 回显同一谓词
    if config is None or not public.configured:
        raise BadRequestError("请先保存飞书 webhook 配置")

    notifier = FeishuWebhookNotifier(webhook_url=config.webhook_url, secret=config.secret)
    ok = await notifier.send(build_test_message())
    if not ok:
        raise BadRequestError("测试消息发送失败，请检查 webhook 地址与签名密钥")
    return Response.success(msg="测试消息已发送，请在群里查收", data=public)
