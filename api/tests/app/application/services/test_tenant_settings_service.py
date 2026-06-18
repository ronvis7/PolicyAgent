"""TenantSettingsService 离线单元测试：按租户隔离 LLM 配置 + 回落平台默认。

异步方法用 asyncio.run 驱动，避免依赖 pytest-asyncio 插件(与本仓库其他测试一致)。
"""

import asyncio

from app.application.services.tenant_settings_service import TenantSettingsService
from app.domain.models.app_config import LLMConfig

from ._fakes import FakeAppConfigRepository, make_uow_factory

# 平台默认 Embedding(来自 AppConfig 默认 EmbedConfig)
PLATFORM_EMBED_MODEL = "text-embedding-v3"
PLATFORM_EMBED_DIM = 1024

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"


def _platform_llm() -> LLMConfig:
    return LLMConfig(api_key="platform-key", model_name="deepseek-reasoner")


def _service() -> TenantSettingsService:
    return TenantSettingsService(
        uow_factory=make_uow_factory(),
        app_config_repository=FakeAppConfigRepository(_platform_llm()),
    )


def test_resolve_falls_back_to_platform_when_unset() -> None:
    """组织未配置时回落平台默认配置，is_custom 为 False"""
    service = _service()

    config, is_custom = asyncio.run(service.resolve_llm_config(TENANT_A))

    assert config.api_key == "platform-key"
    assert is_custom is False


def test_update_then_resolve_uses_tenant_override() -> None:
    """组织配置自有 key 后生效，is_custom 为 True"""
    service = _service()

    asyncio.run(service.update_llm_config(
        TENANT_A, LLMConfig(api_key="tenant-a-key", model_name="custom-model")
    ))
    config, is_custom = asyncio.run(service.resolve_llm_config(TENANT_A))

    assert config.api_key == "tenant-a-key"
    assert config.model_name == "custom-model"
    assert is_custom is True


def test_tenants_are_isolated() -> None:
    """一个组织的覆盖不影响另一个组织"""
    service = _service()

    asyncio.run(service.update_llm_config(TENANT_A, LLMConfig(api_key="tenant-a-key")))
    config_b, is_custom_b = asyncio.run(service.resolve_llm_config(TENANT_B))

    assert config_b.api_key == "platform-key"
    assert is_custom_b is False


def test_empty_api_key_keeps_existing_tenant_key() -> None:
    """更新时 api_key 为空则保留组织已有密钥，仅改其他字段"""
    service = _service()
    asyncio.run(service.update_llm_config(TENANT_A, LLMConfig(api_key="tenant-a-key", max_tokens=4096)))

    asyncio.run(service.update_llm_config(TENANT_A, LLMConfig(api_key="", max_tokens=2048)))
    config, _ = asyncio.run(service.resolve_llm_config(TENANT_A))

    assert config.api_key == "tenant-a-key"
    assert config.max_tokens == 2048


def test_empty_api_key_first_time_falls_back_to_platform_key() -> None:
    """组织从未配置过且首次提交空 api_key 时，沿用平台默认密钥"""
    service = _service()

    asyncio.run(service.update_llm_config(TENANT_A, LLMConfig(api_key="", model_name="m")))
    config, _ = asyncio.run(service.resolve_llm_config(TENANT_A))

    assert config.api_key == "platform-key"


# ---------- Embedding 双轨私有侧(ADR 003)----------


def test_resolve_embed_falls_back_to_platform_when_unset() -> None:
    """组织未配 Embedding key 时回落平台(占位 key 由注入层补 .env)，is_custom 为 False"""
    service = _service()

    config, is_custom = asyncio.run(service.resolve_embed_config(TENANT_A))

    assert is_custom is False
    assert config.model_name == PLATFORM_EMBED_MODEL
    assert config.dimension == PLATFORM_EMBED_DIM


def test_update_embed_then_resolve_uses_tenant_key() -> None:
    """组织配置 Embedding key 后生效，is_custom 为 True"""
    service = _service()

    asyncio.run(service.update_embed_config(TENANT_A, "tenant-embed-key"))
    config, is_custom = asyncio.run(service.resolve_embed_config(TENANT_A))

    assert config.api_key == "tenant-embed-key"
    assert is_custom is True


def test_update_embed_locks_platform_model_and_dimension() -> None:
    """租户只换 key：model/dimension 始终锁平台值，租户改不了(维度恒 1024)"""
    service = _service()

    asyncio.run(service.update_embed_config(TENANT_A, "tenant-embed-key"))
    config, _ = asyncio.run(service.resolve_embed_config(TENANT_A))

    assert config.model_name == PLATFORM_EMBED_MODEL
    assert config.dimension == PLATFORM_EMBED_DIM


def test_embed_tenants_are_isolated() -> None:
    """一个组织的 Embedding key 覆盖不影响另一个组织"""
    service = _service()

    asyncio.run(service.update_embed_config(TENANT_A, "tenant-a-embed-key"))
    config_b, is_custom_b = asyncio.run(service.resolve_embed_config(TENANT_B))

    assert is_custom_b is False
    assert config_b.api_key != "tenant-a-embed-key"


def test_empty_embed_key_first_time_stays_uncovered() -> None:
    """组织从未配置过且首次提交空 Embedding key 时，保持未覆盖(回落平台)"""
    service = _service()

    _, is_custom = asyncio.run(service.update_embed_config(TENANT_A, ""))

    assert is_custom is False
    _, resolved_custom = asyncio.run(service.resolve_embed_config(TENANT_A))
    assert resolved_custom is False


def test_empty_embed_key_keeps_existing_tenant_key() -> None:
    """已配 Embedding key 后再提交空 key，保留组织已有密钥"""
    service = _service()
    asyncio.run(service.update_embed_config(TENANT_A, "tenant-a-embed-key"))

    asyncio.run(service.update_embed_config(TENANT_A, ""))
    config, is_custom = asyncio.run(service.resolve_embed_config(TENANT_A))

    assert config.api_key == "tenant-a-embed-key"
    assert is_custom is True
