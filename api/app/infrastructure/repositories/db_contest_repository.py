from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.contest import ContestDiscoveryHit, ContestSource, ContestSubscription
from app.domain.repositories.contest_repository import ContestRepository
from app.infrastructure.models.contest import ContestDiscoveryHitModel, ContestSourceModel, ContestSubscriptionModel


class DBContestRepository(ContestRepository):
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def list_sources(self, enabled_only: bool = False) -> List[ContestSource]:
        stmt = select(ContestSourceModel).order_by(ContestSourceModel.name)
        if enabled_only:
            stmt = stmt.where(ContestSourceModel.enabled.is_(True))
        return [row.to_domain() for row in (await self.db_session.execute(stmt)).scalars().all()]

    async def get_source(self, source_id: str) -> Optional[ContestSource]:
        row = await self.db_session.get(ContestSourceModel, source_id)
        return row.to_domain() if row else None

    async def get_source_by_key(self, key: str) -> Optional[ContestSource]:
        row = (await self.db_session.execute(select(ContestSourceModel).where(ContestSourceModel.key == key))).scalar_one_or_none()
        return row.to_domain() if row else None

    async def save_source(self, source: ContestSource) -> None:
        row = await self.db_session.get(ContestSourceModel, source.id)
        if row is None:
            self.db_session.add(ContestSourceModel.from_domain(source))
        else:
            row.update_from_domain(source)

    async def delete_source(self, source_id: str) -> bool:
        row = await self.db_session.get(ContestSourceModel, source_id)
        if row is None:
            return False
        await self.db_session.delete(row)
        return True

    async def list_subscriptions(self, tenant_id: str) -> List[ContestSubscription]:
        stmt = select(ContestSubscriptionModel).where(ContestSubscriptionModel.tenant_id == tenant_id).order_by(ContestSubscriptionModel.created_at.desc())
        return [row.to_domain() for row in (await self.db_session.execute(stmt)).scalars().all()]

    async def list_enabled_subscriptions(self) -> List[ContestSubscription]:
        stmt = select(ContestSubscriptionModel).where(ContestSubscriptionModel.enabled.is_(True))
        return [row.to_domain() for row in (await self.db_session.execute(stmt)).scalars().all()]

    async def get_subscription(self, tenant_id: str, subscription_id: str) -> Optional[ContestSubscription]:
        stmt = select(ContestSubscriptionModel).where(ContestSubscriptionModel.tenant_id == tenant_id, ContestSubscriptionModel.id == subscription_id)
        row = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return row.to_domain() if row else None

    async def get_subscription_by_keyword(self, tenant_id: str, keyword: str) -> Optional[ContestSubscription]:
        stmt = select(ContestSubscriptionModel).where(ContestSubscriptionModel.tenant_id == tenant_id, ContestSubscriptionModel.keyword == keyword)
        row = (await self.db_session.execute(stmt)).scalar_one_or_none()
        return row.to_domain() if row else None

    async def save_subscription(self, subscription: ContestSubscription) -> None:
        row = await self.db_session.get(ContestSubscriptionModel, subscription.id)
        if row is None:
            self.db_session.add(ContestSubscriptionModel.from_domain(subscription))
        else:
            row.update_from_domain(subscription)

    async def delete_subscription(self, tenant_id: str, subscription_id: str) -> bool:
        row = (await self.db_session.execute(
            select(ContestSubscriptionModel).where(
                ContestSubscriptionModel.tenant_id == tenant_id,
                ContestSubscriptionModel.id == subscription_id,
            )
        )).scalar_one_or_none()
        if row is None:
            return False
        await self.db_session.delete(row)
        return True

    async def has_discovery_hit(self, tenant_id: str, policy_id: str) -> bool:
        row = (await self.db_session.execute(
            select(ContestDiscoveryHitModel.id).where(
                ContestDiscoveryHitModel.tenant_id == tenant_id,
                ContestDiscoveryHitModel.policy_id == policy_id,
            )
        )).scalar_one_or_none()
        return row is not None

    async def save_discovery_hit(self, hit: ContestDiscoveryHit) -> None:
        self.db_session.add(ContestDiscoveryHitModel.from_domain(hit))
