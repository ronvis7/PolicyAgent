"""租户级设置服务：按租户隔离 LLM 配置(BYO key)，未覆盖时回落平台默认配置。"""

import logging
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from app.application.errors.exceptions import BadRequestError
from app.domain.models.app_config import EmbedConfig, LLMConfig
from app.domain.models.tenant_settings import FeishuNotifyConfig, TenantSettings
from app.domain.repositories.app_config_repository import AppConfigRepository
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)

# 飞书群机器人 webhook 只可能落在官方域名下；服务端会向配置的地址发 POST，
# 收紧到官方 https 前缀防 SSRF(内网/任意外部地址)。larksuite 为国际版。
_ALLOWED_FEISHU_WEBHOOK_PREFIXES = (
    "https://open.feishu.cn/",
    "https://open.larksuite.com/",
)


class TenantSettingsService:
    """租户设置服务，目前负责按租户读写 LLM 配置覆盖"""

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],
            app_config_repository: AppConfigRepository,
    ) -> None:
        self.uow_factory = uow_factory
        self.app_config_repository = app_config_repository

    def _platform_llm_config(self) -> LLMConfig:
        """读取平台默认 LLM 配置(config.yaml)"""
        return self.app_config_repository.load().llm_config

    async def resolve_llm_config(self, tenant_id: str) -> Tuple[LLMConfig, bool]:
        """解析某租户实际生效的 LLM 配置。

        返回 (生效配置, 是否为组织自定义)。组织配置了带非空 api_key 的覆盖则用其覆盖，
        否则回落到平台默认配置。
        """
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
        if settings and settings.llm_config and settings.llm_config.api_key.strip():
            return settings.llm_config, True
        return self._platform_llm_config(), False

    async def get_llm_config(self, tenant_id: str) -> LLMConfig:
        """获取某租户实际生效的 LLM 配置(供 Agent 运行时使用)"""
        llm_config, _ = await self.resolve_llm_config(tenant_id)
        return llm_config

    async def update_llm_config(self, tenant_id: str, new_llm_config: LLMConfig) -> Tuple[LLMConfig, bool]:
        """更新某租户的 LLM 配置覆盖。

        api_key 为空表示不修改密钥：保留组织已有密钥，组织从未配置过则沿用平台默认密钥。
        返回 (保存后的配置, 是否为组织自定义=True)。
        """
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
            existing = settings.llm_config if settings else None

            # 1.api_key 为空则沿用既有密钥(组织已有 → 平台默认)
            if not new_llm_config.api_key.strip():
                fallback_key = (
                    existing.api_key if existing and existing.api_key.strip()
                    else self._platform_llm_config().api_key
                )
                new_llm_config = new_llm_config.model_copy(update={"api_key": fallback_key})

            # 2.组装并保存租户设置(不可变更新)
            record = (settings or TenantSettings(tenant_id=tenant_id)).model_copy(
                update={"llm_config": new_llm_config, "updated_at": datetime.now()}
            )
            await uow.tenant_settings.save(record)

        return new_llm_config, True

    # ---------- Embedding 双轨私有侧：租户只 BYO api_key，其余锁平台(见 ADR 003) ----------

    def _platform_embed_config(self) -> EmbedConfig:
        """读取平台默认 Embedding 运营参数(base_url/model/dimension，来自 config.yaml)。

        注意：返回的 api_key 为 config.yaml 占位(通常空)；平台真实 key 在 .env，由注入层
        (service_dependencies)回落补齐，本服务不接触 .env 以保持分层。
        """
        return self.app_config_repository.load().embed_config

    async def resolve_embed_config(self, tenant_id: str) -> Tuple[EmbedConfig, bool]:
        """解析某租户实际生效的 Embedding 配置。

        始终锁平台的 base_url/model/dimension(保证向量维度恒 1024、同空间)，仅当组织配置了
        非空 api_key 时用其覆盖密钥。返回 (生效配置, 是否为组织自定义)。
        组织未覆盖时返回平台配置(api_key 为占位，由注入层用 .env key 回落)。
        """
        platform = self._platform_embed_config()
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
        if settings and settings.embed_config and settings.embed_config.api_key.strip():
            return platform.model_copy(update={"api_key": settings.embed_config.api_key}), True
        return platform, False

    async def update_embed_config(self, tenant_id: str, api_key: str) -> Tuple[EmbedConfig, bool]:
        """更新某租户的 Embedding 密钥覆盖(租户只能配 api_key，其余锁平台)。

        api_key 非空：设为组织自定义密钥(锁平台其余参数后保存)，返回 (配置, True)。
        api_key 为空：视为"不修改"——已有组织密钥则沿用，从未配置过则保持未覆盖(回落平台)。
        """
        platform = self._platform_embed_config()
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
            existing = settings.embed_config if settings else None

            key = api_key.strip()
            if not key:
                # 不修改密钥：无既有覆盖则保持未覆盖(回落平台)，不写库
                if not (existing and existing.api_key.strip()):
                    return platform, False
                key = existing.api_key

            new_embed = platform.model_copy(update={"api_key": key})
            record = (settings or TenantSettings(tenant_id=tenant_id)).model_copy(
                update={"embed_config": new_embed, "updated_at": datetime.now()}
            )
            await uow.tenant_settings.save(record)

        return new_embed, True

    # ---------- 飞书 webhook 推送配置(组织级"新赛事即推"，前端设置页配置) ----------

    async def get_feishu_config(self, tenant_id: str) -> Optional[FeishuNotifyConfig]:
        """获取某租户的飞书 webhook 配置；None 表示未开启推送"""
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
        return settings.feishu_config if settings else None

    async def update_feishu_config(
            self, tenant_id: str, webhook_url: str, secret: str,
    ) -> FeishuNotifyConfig:
        """保存某租户的飞书 webhook 配置。

        webhook_url 留空=沿用已有地址(前端只回显脱敏 URL，支持只轮换 secret；从未配置过
        则报错)；只认飞书官方域名的 https 地址(服务端会向该地址发请求，防 SSRF)。
        secret 留空：地址未变=不修改已有签名密钥；换了地址=视为新机器人未开签名校验，
        不沿用旧密钥(避免换群后签名错、推送静默失败)。停用推送走 clear_feishu_config。
        """
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
            existing = settings.feishu_config if settings else None

            url = webhook_url.strip()
            if not url:
                if existing is None or not existing.webhook_url.strip():
                    raise BadRequestError("webhook 地址不能为空")
                url = existing.webhook_url
            if not url.startswith(_ALLOWED_FEISHU_WEBHOOK_PREFIXES):
                raise BadRequestError(
                    "仅支持飞书群机器人 webhook 地址(https://open.feishu.cn/ 开头)"
                )

            key = secret.strip()
            if not key and existing and existing.webhook_url == url:
                key = existing.secret  # 地址未变且留空=不修改已有签名密钥

            new_config = FeishuNotifyConfig(webhook_url=url, secret=key)
            record = (settings or TenantSettings(tenant_id=tenant_id)).model_copy(
                update={"feishu_config": new_config, "updated_at": datetime.now()}
            )
            await uow.tenant_settings.save(record)

        return new_config

    async def clear_feishu_config(self, tenant_id: str) -> None:
        """清除某租户的飞书 webhook 配置(停用新赛事推送)；未配置过则无操作"""
        async with self.uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(tenant_id)
            if settings is None or settings.feishu_config is None:
                return
            record = settings.model_copy(
                update={"feishu_config": None, "updated_at": datetime.now()}
            )
            await uow.tenant_settings.save(record)

    async def list_feishu_configured(self) -> List[TenantSettings]:
        """列出配置了飞书 webhook 的租户设置(供新赛事推送扇出)"""
        async with self.uow_factory() as uow:
            return await uow.tenant_settings.list_feishu_configured()
