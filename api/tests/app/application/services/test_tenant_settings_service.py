"""TenantSettingsService 离线单元测试：按租户隔离 LLM 配置 + 回落平台默认。

异步方法用 asyncio.run 驱动，避免依赖 pytest-asyncio 插件(与本仓库其他测试一致)。
"""

import asyncio

import pytest

from app.application.errors.exceptions import BadRequestError
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


# ---------- 飞书 webhook 推送配置(租户级，前端配置替代 env) ----------

FEISHU_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/abcd1234"


def test_feishu_config_unset_returns_none() -> None:
    """组织未配置飞书 webhook 时返回 None(不推送)"""
    service = _service()

    assert asyncio.run(service.get_feishu_config(TENANT_A)) is None


def test_update_then_get_feishu_config() -> None:
    """组织配置 webhook 后可读回(URL+secret)"""
    service = _service()

    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, "sec-1"))
    config = asyncio.run(service.get_feishu_config(TENANT_A))

    assert config is not None
    assert config.webhook_url == FEISHU_URL
    assert config.secret == "sec-1"


def test_update_feishu_empty_secret_keeps_existing() -> None:
    """再次保存时 secret 留空表示不修改，沿用已有签名密钥"""
    service = _service()
    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, "sec-1"))

    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, ""))
    config = asyncio.run(service.get_feishu_config(TENANT_A))

    assert config is not None
    assert config.secret == "sec-1"


def test_update_feishu_requires_webhook_url() -> None:
    """webhook_url 为空时拒绝保存(留空不代表清除，清除走 clear)"""
    service = _service()

    with pytest.raises(BadRequestError):
        asyncio.run(service.update_feishu_config(TENANT_A, "   ", "sec"))


def test_clear_feishu_config_disables_push() -> None:
    """清除配置后读回 None，且不再出现在已配置列表"""
    service = _service()
    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, "sec-1"))

    asyncio.run(service.clear_feishu_config(TENANT_A))

    assert asyncio.run(service.get_feishu_config(TENANT_A)) is None
    assert asyncio.run(service.list_feishu_configured()) == []


def test_list_feishu_configured_returns_only_configured() -> None:
    """已配置列表只含配了 webhook 的租户(其他覆盖如 LLM key 不算)"""
    service = _service()
    asyncio.run(service.update_llm_config(TENANT_B, LLMConfig(api_key="k")))
    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, ""))

    configured = asyncio.run(service.list_feishu_configured())

    assert [s.tenant_id for s in configured] == [TENANT_A]


def test_feishu_config_does_not_disturb_llm_override() -> None:
    """配置 webhook 不影响同租户既有 LLM 覆盖(不可变更新)"""
    service = _service()
    asyncio.run(service.update_llm_config(TENANT_A, LLMConfig(api_key="tenant-a-key")))

    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, "s"))
    llm, is_custom = asyncio.run(service.resolve_llm_config(TENANT_A))

    assert llm.api_key == "tenant-a-key"
    assert is_custom is True


def test_update_feishu_new_url_with_blank_secret_drops_old_secret() -> None:
    """换 webhook 地址且 secret 留空=新机器人未开签名，不沿用旧密钥(避免换群后签名错静默发不出)"""
    service = _service()
    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, "sec-1"))

    new_url = "https://open.feishu.cn/open-apis/bot/v2/hook/other999"
    asyncio.run(service.update_feishu_config(TENANT_A, new_url, ""))
    config = asyncio.run(service.get_feishu_config(TENANT_A))

    assert config is not None
    assert config.webhook_url == new_url
    assert config.secret == ""


def test_update_feishu_blank_url_keeps_existing_when_configured() -> None:
    """已配置后 URL 留空=沿用已有地址(支持只轮换 secret，前端不回显明文 URL)"""
    service = _service()
    asyncio.run(service.update_feishu_config(TENANT_A, FEISHU_URL, "sec-1"))

    asyncio.run(service.update_feishu_config(TENANT_A, "", "sec-2"))
    config = asyncio.run(service.get_feishu_config(TENANT_A))

    assert config is not None
    assert config.webhook_url == FEISHU_URL
    assert config.secret == "sec-2"


def test_update_feishu_rejects_non_feishu_url() -> None:
    """webhook 只认飞书官方域名(https)，防 SSRF(服务端会向该地址发请求)"""
    service = _service()

    for bad in (
        "http://open.feishu.cn/open-apis/bot/v2/hook/x",  # 非 https
        "https://evil.example.com/hook",  # 非飞书域名
        "http://169.254.169.254/latest/meta-data",  # 内网地址
    ):
        with pytest.raises(BadRequestError):
            asyncio.run(service.update_feishu_config(TENANT_A, bad, ""))
