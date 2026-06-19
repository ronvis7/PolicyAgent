"""真仓储跨租户隔离回归(连真库)：验证仓储 SQL 的 tenant 过滤 WHERE 真实生效。

每个用例用两个全新随机租户(A/B)+随机实体 id，互不干扰、无需清库。统一断言模式：
跨租户读/删 → 取不到/不生效；本租户 → 取得到/生效(与手动探针、内存隔离套件同口径)。
"""

import asyncio
import uuid

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType
from app.domain.models.knowledge_base import KnowledgeBase, KnowledgeBaseType
from app.domain.models.session import Session
from app.domain.models.tenant import Tenant


def _tid() -> str:
    return f"itest-{uuid.uuid4()}"


async def _seed_tenant(uow_factory, tenant_id: str) -> None:
    """种一个租户行(其余被测表的 tenant_id FK 指向它)。"""
    async with uow_factory() as uow:
        await uow.tenant.save(Tenant(id=tenant_id, name=tenant_id, slug=tenant_id))


def test_session_repo_isolation(uow_factory):
    async def body():
        a, b = _tid(), _tid()
        await _seed_tenant(uow_factory, a)
        await _seed_tenant(uow_factory, b)

        sid = str(uuid.uuid4())
        async with uow_factory() as uow:
            await uow.session.save(Session(id=sid, tenant_id=a, title="A 的会话"))

        async with uow_factory() as uow:
            assert await uow.session.get_by_id(sid, b) is None       # 跨租户读不到
            assert await uow.session.get_by_id(sid, a) is not None    # 本租户读得到
            assert [s.id for s in await uow.session.get_all(b)] == []  # B 列表里没有 A 的
            assert sid in [s.id for s in await uow.session.get_all(a)]

        # B 删 A 的会话应不生效；A 自己删才生效
        async with uow_factory() as uow:
            await uow.session.delete_by_id(sid, b)
        async with uow_factory() as uow:
            assert await uow.session.get_by_id(sid, a) is not None
            await uow.session.delete_by_id(sid, a)
        async with uow_factory() as uow:
            assert await uow.session.get_by_id(sid, a) is None

    asyncio.run(body())


def test_knowledge_base_repo_isolation(uow_factory):
    async def body():
        a, b = _tid(), _tid()
        await _seed_tenant(uow_factory, a)
        await _seed_tenant(uow_factory, b)

        kid = str(uuid.uuid4())
        async with uow_factory() as uow:
            await uow.knowledge_base.save(KnowledgeBase(
                id=kid, tenant_id=a, name="A 库", type=KnowledgeBaseType.GENERAL,
            ))

        async with uow_factory() as uow:
            assert await uow.knowledge_base.get_by_id(kid, b) is None
            assert await uow.knowledge_base.get_by_id(kid, a) is not None
            assert kid not in [k.id for k in await uow.knowledge_base.list_by_tenant(b)]
            assert kid in [k.id for k in await uow.knowledge_base.list_by_tenant(a)]

        # B 删 A 的库不生效
        async with uow_factory() as uow:
            await uow.knowledge_base.delete(kid, b)
        async with uow_factory() as uow:
            assert await uow.knowledge_base.get_by_id(kid, a) is not None

    asyncio.run(body())


def test_enterprise_profile_repo_isolation(uow_factory):
    async def body():
        a, b = _tid(), _tid()
        await _seed_tenant(uow_factory, a)
        await _seed_tenant(uow_factory, b)

        async with uow_factory() as uow:
            await uow.enterprise_profile.save(
                EnterpriseProfile(tenant_id=a, company_name="A 公司"),
            )

        async with uow_factory() as uow:
            assert await uow.enterprise_profile.get_by_tenant(b) is None  # B 没有自己的档案
            mine = await uow.enterprise_profile.get_by_tenant(a)
            assert mine is not None and mine.company_name == "A 公司"

    asyncio.run(body())


def test_feed_repo_isolation(uow_factory):
    async def body():
        a, b = _tid(), _tid()
        # policy_matches.tenant_id 无 FK，但仍按租户隔离；种租户行以贴近真实
        await _seed_tenant(uow_factory, a)
        await _seed_tenant(uow_factory, b)

        fid = str(uuid.uuid4())
        async with uow_factory() as uow:
            await uow.feed.save(FeedItem(
                id=fid, tenant_id=a, type=FeedItemType.POLICY, policy_id="p1", title="A 机会",
            ))

        async with uow_factory() as uow:
            assert await uow.feed.get_by_id(b, fid) is None     # 跨租户读不到
            assert await uow.feed.get_by_id(a, fid) is not None  # 本租户读得到

    asyncio.run(body())
