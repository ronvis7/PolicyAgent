"""离线测试用的内存级 UoW 与仓库假实现，避免依赖真实 Postgres/Redis。"""

from datetime import date
from typing import Callable, Dict, List, Optional

from app.domain.models.agent_memory import AgentMemory
from app.domain.models.app_config import AgentConfig, AppConfig, A2AConfig, LLMConfig, MCPConfig
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.intel_briefing import IntelBriefing
from app.domain.models.feed_item import FeedItem, FeedStatus
from app.domain.models.knowledge_base import KnowledgeBase
from app.domain.models.knowledge_file import KnowledgeFile
from app.domain.models.membership import Membership
from app.domain.models.policy import Policy
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

    async def list_tenant_ids(self) -> List[str]:
        return list(self._store.keys())


class FakeIntelBriefingRepository:
    """内存级主动情报简报仓库（每租户一份，覆盖式）。"""

    def __init__(self, store: Dict[str, IntelBriefing]) -> None:
        self._store = store

    async def get_by_tenant(self, tenant_id: str) -> Optional[IntelBriefing]:
        return self._store.get(tenant_id)

    async def save(self, briefing: IntelBriefing) -> None:
        self._store[briefing.tenant_id] = briefing


class FakePolicyRepository:
    """内存级公开政策仓库，按 source_url upsert，支持简单分页与筛选。"""

    def __init__(self, store: Dict[str, Policy]) -> None:
        self._store = store  # 以 source_url 为键，模拟唯一约束

    async def get_by_id(self, policy_id: str) -> Optional[Policy]:
        return next((p for p in self._store.values() if p.id == policy_id), None)

    async def get_by_source_url(self, source_url: str) -> Optional[Policy]:
        return self._store.get(source_url)

    async def list_by_source_urls(self, source_urls: List[str]) -> List[Policy]:
        return [self._store[u] for u in source_urls if u in self._store]

    async def save(self, policy: Policy) -> None:
        existing = self._store.get(policy.source_url)
        if existing:
            # 模拟 upsert：保留原 id/created_at，覆盖业务字段
            policy = policy.model_copy(update={"id": existing.id, "created_at": existing.created_at})
        self._store[policy.source_url] = policy

    async def list_paginated(
        self, page: int, page_size: int, region: str = "", issuer: str = "", keyword: str = "",
    ):
        items = list(self._store.values())
        if region:
            items = [p for p in items if region in p.region]
        if issuer:
            items = [p for p in items if issuer in p.issuer]
        if keyword:
            items = [p for p in items if keyword in p.title]
        total = len(items)
        items.sort(key=lambda p: p.publish_date or date.min, reverse=True)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def list_candidates(self, limit: int):
        items = sorted(
            self._store.values(), key=lambda p: p.publish_date or date.min, reverse=True
        )
        return items[:limit]

    async def stats_by_source(self):
        """按来源聚合：{source: (条数, 最近抓取时间)}"""
        stats: Dict[str, tuple] = {}
        for p in self._store.values():
            cnt, last = stats.get(p.source, (0, None))
            crawled = getattr(p, "crawled_at", None)
            if crawled is not None and (last is None or crawled > last):
                last = crawled
            stats[p.source] = (cnt + 1, last)
        return stats


class FakeFeedRepository:
    """内存级工作台 Feed 仓库，按 (tenant_id, policy_id) upsert。"""

    def __init__(self, store: Dict[str, FeedItem]) -> None:
        self._store = store  # 以 id 为键

    def _key(self, tenant_id: str, policy_id: str):
        return (tenant_id, policy_id)

    async def get_by_tenant_and_policy(
        self, tenant_id: str, policy_id: str,
    ) -> Optional[FeedItem]:
        return next(
            (i for i in self._store.values()
             if i.tenant_id == tenant_id and i.policy_id == policy_id),
            None,
        )

    async def get_by_id(self, tenant_id: str, item_id: str) -> Optional[FeedItem]:
        item = self._store.get(item_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def save(self, item: FeedItem) -> None:
        existing = await self.get_by_tenant_and_policy(item.tenant_id, item.policy_id)
        if existing and existing.id != item.id:
            # 模拟自然键唯一约束：复用既有行 id
            item = item.model_copy(update={"id": existing.id})
        self._store[item.id] = item

    async def list_paginated(self, tenant_id, status, page, page_size):
        items = [i for i in self._store.values() if i.tenant_id == tenant_id]
        if status is not None:
            items = [i for i in items if i.status == status]
        total = len(items)
        items.sort(key=lambda i: i.created_at, reverse=True)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def count_by_status(self, tenant_id: str, status: FeedStatus) -> int:
        return sum(
            1 for i in self._store.values()
            if i.tenant_id == tenant_id and i.status == status
        )

    async def list_expiring(self, tenant_id, today, until):
        items = [
            i for i in self._store.values()
            if i.tenant_id == tenant_id
            and i.deadline_status == "extracted"
            and i.apply_deadline is not None
            and today <= i.apply_deadline <= until
            and i.status != FeedStatus.IGNORED
        ]
        items.sort(key=lambda i: i.apply_deadline)
        return items

    async def mark_all_read(self, tenant_id: str) -> int:
        count = 0
        for item_id, item in list(self._store.items()):
            if item.tenant_id == tenant_id and item.status == FeedStatus.UNREAD:
                self._store[item_id] = item.model_copy(update={"status": FeedStatus.READ})
                count += 1
        return count


class FakeKnowledgeBaseRepository:
    def __init__(self, store: Dict[str, KnowledgeBase]) -> None:
        self._store = store

    async def get_by_id(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBase]:
        kb = self._store.get(kb_id)
        if kb and tenant_id is not None and kb.tenant_id != tenant_id:
            return None
        return kb

    async def save(self, kb: KnowledgeBase) -> None:
        self._store[kb.id] = kb


class FakeKnowledgeFileRepository:
    def __init__(self, store: Dict[str, KnowledgeFile]) -> None:
        self._store = store

    async def save(self, kf: KnowledgeFile) -> None:
        self._store[kf.id] = kf

    async def get_by_id(self, kf_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeFile]:
        return self._store.get(kf_id)


class FakeDocumentChunkRepository:
    """内存级切片仓库，按 knowledge_file_id 分组记录(chunk, vector)。"""

    def __init__(self, store: Dict[str, list]) -> None:
        self._store = store  # knowledge_file_id -> List[(chunk, vector)]

    async def delete_by_knowledge_file(self, knowledge_file_id: str, tenant_id: str) -> None:
        self._store.pop(knowledge_file_id, None)

    async def add_many(self, chunks_with_vectors: list) -> None:
        for chunk, vector in chunks_with_vectors:
            self._store.setdefault(chunk.knowledge_file_id, []).append((chunk, vector))

    async def search_similar(
        self, knowledge_base_id: str, tenant_id: str, query_embedding: list, top_k: int = 5,
    ):
        """内存级相似检索：按库/租户过滤后算余弦相似度，按相似度倒序取 top_k。"""
        def _cosine(a: list, b: list) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        scored = []
        for chunks in self._store.values():
            for chunk, vector in chunks:
                if chunk.knowledge_base_id == knowledge_base_id and chunk.tenant_id == tenant_id:
                    scored.append((chunk, _cosine(query_embedding, vector)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


class FakeEmbedding:
    """固定维度的假 Embedding，按文本数返回等长向量。"""

    @property
    def model_name(self) -> str:
        return "fake-embed"

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def embed_query(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3]


class FakeAgentMemoryRepository:
    """内存级 Agent 长期记忆仓库，按租户过滤、按创建时间倒序返回。"""

    def __init__(self, store: Dict[str, AgentMemory]) -> None:
        self._store = store

    async def list_by_tenant(self, tenant_id: str, limit: int = 0) -> List[AgentMemory]:
        items = [m for m in self._store.values() if m.tenant_id == tenant_id]
        items.sort(key=lambda m: m.created_at, reverse=True)
        return items[:limit] if limit and limit > 0 else items

    async def add(self, memory: AgentMemory) -> None:
        self._store[memory.id] = memory

    async def delete(self, tenant_id: str, memory_id: str) -> bool:
        item = self._store.get(memory_id)
        if item is None or item.tenant_id != tenant_id:
            return False
        del self._store[memory_id]
        return True


class FakeUnitOfWork:
    """共享底层 store 的内存级 UoW，commit/flush/rollback 均为空操作。"""

    def __init__(
            self,
            users: Dict[str, User],
            memberships: Dict[str, Membership],
            tenant_settings: Dict[str, TenantSettings],
            tenants: Dict[str, Tenant],
            enterprise_profiles: Dict[str, EnterpriseProfile],
            policies: Dict[str, Policy],
            feed_items: Dict[str, FeedItem],
            knowledge_bases: Dict[str, KnowledgeBase],
            knowledge_files: Dict[str, KnowledgeFile],
            document_chunks: Dict[str, list],
            agent_memories: Dict[str, AgentMemory],
            intel_briefings: Dict[str, IntelBriefing],
    ) -> None:
        self.user = FakeUserRepository(users)
        self.membership = FakeMembershipRepository(memberships)
        self.tenant_settings = FakeTenantSettingsRepository(tenant_settings)
        self.tenant = FakeTenantRepository(tenants)
        self.enterprise_profile = FakeEnterpriseProfileRepository(enterprise_profiles)
        self.policy = FakePolicyRepository(policies)
        self.feed = FakeFeedRepository(feed_items)
        self.knowledge_base = FakeKnowledgeBaseRepository(knowledge_bases)
        self.knowledge_file = FakeKnowledgeFileRepository(knowledge_files)
        self.document_chunk = FakeDocumentChunkRepository(document_chunks)
        self.agent_memory = FakeAgentMemoryRepository(agent_memories)
        self.intel_briefing = FakeIntelBriefingRepository(intel_briefings)

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
        policies: Optional[Dict[str, Policy]] = None,
        feed_items: Optional[Dict[str, FeedItem]] = None,
        knowledge_bases: Optional[Dict[str, KnowledgeBase]] = None,
        knowledge_files: Optional[Dict[str, KnowledgeFile]] = None,
        document_chunks: Optional[Dict[str, list]] = None,
        agent_memories: Optional[Dict[str, AgentMemory]] = None,
        intel_briefings: Optional[Dict[str, IntelBriefing]] = None,
) -> Callable[[], FakeUnitOfWork]:
    """构造一个每次返回新 UoW、但共享同一底层 store 的工厂(模拟跨事务持久化)。"""
    users = users if users is not None else {}
    memberships = memberships if memberships is not None else {}
    tenant_settings = tenant_settings if tenant_settings is not None else {}
    tenants = tenants if tenants is not None else {}
    enterprise_profiles = enterprise_profiles if enterprise_profiles is not None else {}
    policies = policies if policies is not None else {}
    feed_items = feed_items if feed_items is not None else {}
    knowledge_bases = knowledge_bases if knowledge_bases is not None else {}
    knowledge_files = knowledge_files if knowledge_files is not None else {}
    document_chunks = document_chunks if document_chunks is not None else {}
    agent_memories = agent_memories if agent_memories is not None else {}
    intel_briefings = intel_briefings if intel_briefings is not None else {}

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(
            users, memberships, tenant_settings, tenants, enterprise_profiles,
            policies, feed_items, knowledge_bases, knowledge_files, document_chunks,
            agent_memories, intel_briefings,
        )

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
