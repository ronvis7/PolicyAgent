from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.contest import ContestDiscoveryHit, ContestRun, ContestSource, ContestSubscription, TenantContestSource
from app.domain.repositories.contest_repository import ContestRepository
from app.infrastructure.models.contest import ContestDiscoveryHitModel, ContestRunModel, ContestSourceModel, ContestSubscriptionModel, TenantContestSourceItemModel, TenantContestSourceModel


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

    async def list_tenant_sources(self, tenant_id: str, enabled_only: bool = False) -> List[TenantContestSource]:
        stmt = select(TenantContestSourceModel).where(TenantContestSourceModel.tenant_id == tenant_id)
        if enabled_only:
            stmt = stmt.where(TenantContestSourceModel.enabled.is_(True))
        rows = (await self.db_session.execute(stmt.order_by(TenantContestSourceModel.created_at.desc()))).scalars().all()
        return [row.to_domain() for row in rows]

    async def list_enabled_tenant_sources(self) -> List[TenantContestSource]:
        rows = (await self.db_session.execute(select(TenantContestSourceModel).where(TenantContestSourceModel.enabled.is_(True)))).scalars().all()
        return [row.to_domain() for row in rows]

    async def get_tenant_source(self, tenant_id: str, source_id: str) -> Optional[TenantContestSource]:
        row = (await self.db_session.execute(select(TenantContestSourceModel).where(
            TenantContestSourceModel.tenant_id == tenant_id, TenantContestSourceModel.id == source_id,
        ))).scalar_one_or_none()
        return row.to_domain() if row else None

    async def save_tenant_source(self, source: TenantContestSource) -> None:
        row = await self.db_session.get(TenantContestSourceModel, source.id)
        if row is None:
            self.db_session.add(TenantContestSourceModel.from_domain(source))
        elif row.tenant_id == source.tenant_id:
            row.update_from_domain(source)

    async def delete_tenant_source(self, tenant_id: str, source_id: str) -> bool:
        row = await self.db_session.get(TenantContestSourceModel, source_id)
        if row is None or row.tenant_id != tenant_id:
            return False
        await self.db_session.delete(row)
        return True

    async def link_tenant_source_policy(self, tenant_id: str, source_id: str, policy_id: str) -> None:
        existing = (await self.db_session.execute(select(TenantContestSourceItemModel.id).where(
            TenantContestSourceItemModel.tenant_id == tenant_id,
            TenantContestSourceItemModel.source_id == source_id,
            TenantContestSourceItemModel.policy_id == policy_id,
        ))).scalar_one_or_none()
        if existing is None:
            self.db_session.add(TenantContestSourceItemModel(tenant_id=tenant_id, source_id=source_id, policy_id=policy_id))

    async def tenant_can_view_policy(self, tenant_id: str, policy_id: str) -> bool:
        value = (await self.db_session.execute(select(TenantContestSourceItemModel.id).where(
            TenantContestSourceItemModel.tenant_id == tenant_id, TenantContestSourceItemModel.policy_id == policy_id,
        ))).scalar_one_or_none()
        return value is not None

    async def save_run(self, run: ContestRun) -> None:
        row = await self.db_session.get(ContestRunModel, run.id)
        if row is None:
            self.db_session.add(ContestRunModel.from_domain(run))
        else:
            row.update_from_domain(run)

    async def list_runs(self, tenant_id: str, kind: str, target_id: str, limit: int = 10) -> List[ContestRun]:
        rows = (await self.db_session.execute(select(ContestRunModel).where(
            ContestRunModel.tenant_id == tenant_id, ContestRunModel.kind == kind, ContestRunModel.target_id == target_id,
        ).order_by(ContestRunModel.started_at.desc()).limit(limit))).scalars().all()
        return [row.to_domain() for row in rows]
