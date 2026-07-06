"""tenant_settings 仓储 SQL 回归(连真库)：list_feishu_configured 的 IS NOT NULL 过滤。

SQLAlchemy JSON 列默认把 Python None 序列化为 JSONB 'null'(而 'null'::jsonb IS NOT NULL
在 Postgres 里为真)，会让过滤匹配所有 tenant_settings 行；ORM 侧用 none_as_null=True 让
显式 None 落 SQL NULL，本用例做回归——内存 fake 仓储测不到这层。
"""

import asyncio
import uuid

from app.domain.models.app_config import LLMConfig
from app.domain.models.tenant import Tenant
from app.domain.models.tenant_settings import FeishuNotifyConfig, TenantSettings


def test_list_feishu_configured_matches_only_real_configs(uow_factory):
    async def body():
        a, b = f"itest-{uuid.uuid4()}", f"itest-{uuid.uuid4()}"
        async with uow_factory() as uow:
            await uow.tenant.save(Tenant(id=a, name=a, slug=a))
            await uow.tenant.save(Tenant(id=b, name=b, slug=b))

        # A 只配 LLM key(feishu_config 显式 None)；B 配了 webhook
        async with uow_factory() as uow:
            await uow.tenant_settings.save(
                TenantSettings(tenant_id=a, llm_config=LLMConfig(api_key="k")),
            )
            await uow.tenant_settings.save(TenantSettings(
                tenant_id=b,
                feishu_config=FeishuNotifyConfig(
                    webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/x",
                ),
            ))

        async with uow_factory() as uow:
            listed = {s.tenant_id for s in await uow.tenant_settings.list_feishu_configured()}
        assert b in listed
        assert a not in listed  # JSONB 'null' 误匹配时会挂在这

        # B 清除配置(update 写显式 None)后不再出现
        async with uow_factory() as uow:
            settings = await uow.tenant_settings.get_by_tenant(b)
            await uow.tenant_settings.save(settings.model_copy(update={"feishu_config": None}))
        async with uow_factory() as uow:
            listed = {s.tenant_id for s in await uow.tenant_settings.list_feishu_configured()}
        assert b not in listed

    asyncio.run(body())
