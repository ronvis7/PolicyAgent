"""企业档案服务：按租户读写组织级结构化档案。

作为"以企业为主体"主动服务链路的源头。本期只承载结构化档案的读写；
Agent 联网增强(①b)后续在此扩展。
"""

import logging
from datetime import datetime
from typing import Callable

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.repositories.uow import IUnitOfWork

logger = logging.getLogger(__name__)


class EnterpriseProfileService:
    """企业档案服务，按租户读写结构化档案(每个租户一条)"""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_profile(self, tenant_id: str) -> EnterpriseProfile:
        """获取某租户的企业档案。

        从未填写过则返回带默认地区(无锡新吴区)的空档案，便于前端直接渲染表单。
        """
        async with self.uow_factory() as uow:
            profile = await uow.enterprise_profile.get_by_tenant(tenant_id)
        return profile or EnterpriseProfile(tenant_id=tenant_id)

    async def update_profile(self, tenant_id: str, new_profile: EnterpriseProfile) -> EnterpriseProfile:
        """更新某租户的企业档案(不存在则创建)。

        以传入档案为准做整体覆盖；tenant_id/created_at 以服务端为准，避免被客户端篡改。
        """
        async with self.uow_factory() as uow:
            existing = await uow.enterprise_profile.get_by_tenant(tenant_id)

            # 整体覆盖业务字段；保留原 created_at，刷新 updated_at，强制绑定当前租户
            record = new_profile.model_copy(update={
                "tenant_id": tenant_id,
                "created_at": existing.created_at if existing else datetime.now(),
                "updated_at": datetime.now(),
            })
            await uow.enterprise_profile.save(record)

        return record
