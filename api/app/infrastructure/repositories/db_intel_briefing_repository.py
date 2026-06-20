from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.intel_briefing import IntelBriefing
from app.domain.repositories.intel_briefing_repository import IntelBriefingRepository
from app.infrastructure.models import IntelBriefingModel


class DBIntelBriefingRepository(IntelBriefingRepository):
    """基于 Postgres 的主动情报简报仓库（每租户一行，覆盖式保存）。"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def get_by_tenant(self, tenant_id: str) -> Optional[IntelBriefing]:
        stmt = select(IntelBriefingModel).where(IntelBriefingModel.tenant_id == tenant_id)
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def save(self, briefing: IntelBriefing) -> None:
        stmt = select(IntelBriefingModel).where(
            IntelBriefingModel.tenant_id == briefing.tenant_id
        )
        record = (await self.db_session.execute(stmt)).scalar_one_or_none()
        if not record:
            self.db_session.add(IntelBriefingModel.from_domain(briefing))
            return
        record.update_from_domain(briefing)
