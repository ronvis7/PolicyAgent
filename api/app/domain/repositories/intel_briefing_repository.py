from typing import Optional, Protocol

from app.domain.models.intel_briefing import IntelBriefing


class IntelBriefingRepository(Protocol):
    """主动情报简报仓库协议（每租户最新一份）。"""

    async def get_by_tenant(self, tenant_id: str) -> Optional[IntelBriefing]:
        """读取某租户最新一份情报简报（无则 None）。"""
        ...

    async def save(self, briefing: IntelBriefing) -> None:
        """覆盖式保存某租户的情报简报（不存在则创建）。"""
        ...
