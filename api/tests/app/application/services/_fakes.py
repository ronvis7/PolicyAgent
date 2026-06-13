"""离线测试用的内存级 UoW 与仓库假实现，避免依赖真实 Postgres/Redis。"""

from typing import Callable, Dict, List, Optional

from app.domain.models.app_config import AgentConfig, AppConfig, A2AConfig, LLMConfig, MCPConfig
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.membership import Membership
from app.domain.models.tenant import Tenant
from app.domain.models.tenant_settings import TenantSettings
from app.domain.models.user import User


class FakeUserRepository:
    def __init__(self, store: Dict[str, User]) -> None:
        self._store = store

    async def get_by_id(self, user_id: str) -> Optional[User]:
        return self._store.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        return next((u for u in self._store.values() if u.email == email), None)

    async def save(self, user: User) -> None:
        self._store[user.id] = user


class FakeMembershipRepository:
    def __init__(self, store: Dict[str, Membership]) -> None:
        self._store = store

    async def save(self, membership: Membership) -> None:
        self._store[membership.id] = membership

    async def get_by_user_and_tenant(self, user_id: str, tenant_id: str) -> Optional[Membership]:
        return next(
            (m for m in self._store.values() if m.user_id == user_id and m.tenant_id == tenant_id),
            None,
        )

    async def list_by_user(self, user_id: str) -> List[Membership]:
        return [m for m in self._store.values() if m.user_id == user_id]

    async def list_by_tenant(self, tenant_id: str) -> List[Membership]:
        items = [m for m in self._store.values() if m.tenant_id == tenant_id]
        return sorted(items, key=lambda m: m.created_at)


class FakeTenantRepository:
    def __init__(self, store: Dict[str, Tenant]) -> None:
        self._store = store

    async def save(self, tenant: Tenant) -> None:
        self._store[tenant.id] = tenant

    async def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        return self._store.get(tenant_id)

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        return next((t for t in self._store.values() if t.slug == slug), None)

    async def get_shared_by_name(self, name: str) -> Optional[Tenant]:
        normalized = name.strip().lower()
        return next(
            (t for t in self._store.values()
             if not t.is_personal and t.name.strip().lower() == normalized),
            None,
        )

    async def list_shared(self, query: str = "", limit: int = 20) -> List[Tenant]:
        normalized = query.strip().lower()
        items = [
            t for t in self._store.values()
            if not t.is_personal and (not normalized or normalized in t.name.lower())
        ]
        return sorted(items, key=lambda t: t.created_at)[:limit]


class FakeTenantSettingsRepository:
    def __init__(self, store: Dict[str, TenantSettings]) -> None:
        self._store = store

    async def get_by_tenant(self, tenant_id: str) -> Optional[TenantSettings]:
        return self._store.get(tenant_id)

    async def save(self, settings: TenantSettings) -> None:
        self._store[settings.tenant_id] = settings


class FakeEnterpriseProfileRepository:
    def __init__(self, store: Dict[str, EnterpriseProfile]) -> None:
        self._store = store

    async def get_by_tenant(self, tenant_id: str) -> Optional[EnterpriseProfile]:
        return self._store.get(tenant_id)

    async def save(self, profile: EnterpriseProfile) -> None:
        self._store[profile.tenant_id] = profile


class FakeUnitOfWork:
    """共享底层 store 的内存级 UoW，commit/flush/rollback 均为空操作。"""

    def __init__(
            self,
            users: Dict[str, User],
            memberships: Dict[str, Membership],
            tenant_settings: Dict[str, TenantSettings],
            tenants: Dict[str, Tenant],
            enterprise_profiles: Dict[str, EnterpriseProfile],
    ) -> None:
        self.user = FakeUserRepository(users)
        self.membership = FakeMembershipRepository(memberships)
        self.tenant_settings = FakeTenantSettingsRepository(tenant_settings)
        self.tenant = FakeTenantRepository(tenants)
        self.enterprise_profile = FakeEnterpriseProfileRepository(enterprise_profiles)

    async def commit(self) -> None: ...
    async def flush(self) -> None: ...
    async def rollback(self) -> None: ...

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


def make_uow_factory(
        users: Optional[Dict[str, User]] = None,
        memberships: Optional[Dict[str, Membership]] = None,
        tenant_settings: Optional[Dict[str, TenantSettings]] = None,
        tenants: Optional[Dict[str, Tenant]] = None,
        enterprise_profiles: Optional[Dict[str, EnterpriseProfile]] = None,
) -> Callable[[], FakeUnitOfWork]:
    """构造一个每次返回新 UoW、但共享同一底层 store 的工厂(模拟跨事务持久化)。"""
    users = users if users is not None else {}
    memberships = memberships if memberships is not None else {}
    tenant_settings = tenant_settings if tenant_settings is not None else {}
    tenants = tenants if tenants is not None else {}
    enterprise_profiles = enterprise_profiles if enterprise_profiles is not None else {}

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(users, memberships, tenant_settings, tenants, enterprise_profiles)

    return factory


class FakeAppConfigRepository:
    """内存级平台配置仓库，仅承载默认 LLM 配置。"""

    def __init__(self, llm_config: LLMConfig) -> None:
        self._config = AppConfig(
            llm_config=llm_config,
            agent_config=AgentConfig(),
            mcp_config=MCPConfig(),
            a2a_config=A2AConfig(),
        )

    def load(self) -> AppConfig:
        return self._config

    def save(self, app_config: AppConfig) -> None:
        self._config = app_config
