"""租户赛事搜索配置接口的凭据回显回归测试。"""

import asyncio
from types import SimpleNamespace

from app.domain.models.tenant_settings import ContestSearchConfig
from app.interfaces.endpoints.tenant_search_routes import (
    get_contest_search_config,
    update_contest_search_config,
)
from app.interfaces.schemas.app_config import UpdateContestSearchConfigRequest


class _Service:
    def __init__(self) -> None:
        self.config = None
        self.updated = None

    async def get_contest_search_config(self, tenant_id: str):
        assert tenant_id == "tenant-a"
        return self.config

    async def update_contest_search_config(self, tenant_id: str, api_key: str):
        assert tenant_id == "tenant-a"
        self.updated = api_key
        self.config = ContestSearchConfig(api_key=api_key)
        return self.config


def test_update_does_not_echo_api_key() -> None:
    service = _Service()
    response = asyncio.run(update_contest_search_config(
        UpdateContestSearchConfigRequest(api_key="secret-baidu-key"),
        SimpleNamespace(tenant_id="tenant-a"),
        service,
    ))

    assert service.updated == "secret-baidu-key"
    assert response.data is not None
    assert "api_key" not in response.data.model_dump()
    assert response.data.is_custom is True


def test_get_only_returns_configuration_state() -> None:
    service = _Service()
    service.config = ContestSearchConfig(api_key="stored-secret")

    response = asyncio.run(get_contest_search_config(
        SimpleNamespace(tenant_id="tenant-a"), service,
    ))

    assert response.data is not None
    assert "stored-secret" not in response.model_dump_json()
    assert response.data.is_custom is True
