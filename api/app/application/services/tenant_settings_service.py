"""租户级设置服务：按租户隔离 LLM 配置(BYO key)，未覆盖时回落平台默认配置。"""

import logging
from datetime import datetime
from typing import Callable, Tuple

from app.domain.models.app_config import LLMConfig
from app.domain.models.tenant_settings import TenantSettings
from app.domain.repositories.app_config_repository import AppConfigRepository
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)


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
