"""Contest source and discovery service unit tests without external services."""

import asyncio
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from app.application.errors.exceptions import NotFoundError
from app.application.services.contest_service import ContestService
from app.domain.models.contest import ContestDiscoveryHit, ContestSource, ContestSubscription
from app.domain.models.policy import Policy
from app.domain.models.search import SearchResultItem, SearchResults
from app.domain.models.tool_result import ToolResult

from ._fakes import FakePolicyRepository


class _ContestRepo:
    def __init__(self) -> None:
        self.sources: Dict[str, ContestSource] = {}
        self.subscriptions: Dict[str, ContestSubscription] = {}
        self.hits: List[ContestDiscoveryHit] = []

    async def list_sources(self, enabled_only=False):
        return [source for source in self.sources.values() if not enabled_only or source.enabled]

    async def get_source(self, source_id):
        return self.sources.get(source_id)

    async def get_source_by_key(self, key):
        return next((source for source in self.sources.values() if source.key == key), None)

    async def save_source(self, source):
        self.sources[source.id] = source

    async def delete_source(self, source_id):
        return self.sources.pop(source_id, None) is not None

    async def list_subscriptions(self, tenant_id):
        return [sub for sub in self.subscriptions.values() if sub.tenant_id == tenant_id]

    async def list_enabled_subscriptions(self):
        return [sub for sub in self.subscriptions.values() if sub.enabled]

    async def get_subscription(self, tenant_id, subscription_id):
        sub = self.subscriptions.get(subscription_id)
        return sub if sub and sub.tenant_id == tenant_id else None

    async def get_subscription_by_keyword(self, tenant_id, keyword):
        return next((sub for sub in self.subscriptions.values()
                     if sub.tenant_id == tenant_id and sub.keyword == keyword), None)

    async def save_subscription(self, subscription):
        self.subscriptions[subscription.id] = subscription

    async def delete_subscription(self, tenant_id, subscription_id):
        if not await self.get_subscription(tenant_id, subscription_id):
            return False
        del self.subscriptions[subscription_id]
        return True

    async def has_discovery_hit(self, tenant_id, policy_id):
        return any(hit.tenant_id == tenant_id and hit.policy_id == policy_id for hit in self.hits)

    async def save_discovery_hit(self, hit):
        self.hits.append(hit)


class _Uow:
    def __init__(self, contest, policy) -> None:
        self.contest, self.policy = contest, policy

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Search:
    def __init__(self) -> None:
        self.calls = []

    async def invoke(self, query, date_range=None):
        self.calls.append((query, date_range))
        return ToolResult(success=True, data=SearchResults(
            query=query,
            results=[SearchResultItem(
                title="创新创业大赛报名通知",
                snippet="报名参赛，请查看官方通知",
                url="https://example.test/contest-1",
            )],
        ))


class _Ingest:
    def __init__(self, policies) -> None:
        self._policies = policies

    async def ingest_with_crawler(self, source, crawler, name, **kwargs):
        for policy in await crawler.crawl():
            existing = self._policies.get(policy.source_url)
            self._policies[policy.source_url] = policy.model_copy(
                update={"id": existing.id if existing else policy.id}
            )
        return {"source": source, "crawled": 1, "new": 1}


def _service(contest: _ContestRepo, policies: Dict[str, Policy], notified=None, search=None) -> ContestService:
    def factory():
        return _Uow(contest, FakePolicyRepository(policies))
    return ContestService(factory, search or _Search(), on_tenant_discovered=notified)


def test_subscription_cannot_be_read_or_changed_by_another_tenant() -> None:
    contest, policies = _ContestRepo(), {}
    service = _service(contest, policies)
    sub = asyncio.run(service.create_subscription("tenant-a", "人工智能"))

    assert asyncio.run(service.list_subscriptions("tenant-b")) == []
    with pytest.raises(NotFoundError):
        asyncio.run(service.update_subscription("tenant-b", sub.id, False))
    with pytest.raises(NotFoundError):
        asyncio.run(service.delete_subscription("tenant-b", sub.id))
    assert asyncio.run(service.list_subscriptions("tenant-a"))[0].id == sub.id


def test_discovery_is_publicly_deduped_and_notified_once_per_tenant() -> None:
    contest, policies, notified = _ContestRepo(), {}, []

    async def on_discovered(tenant_id: str, rows: List[Policy]) -> None:
        notified.append((tenant_id, [row.source_url for row in rows]))

    service = _service(contest, policies, on_discovered)
    a = asyncio.run(service.create_subscription("tenant-a", "人工智能"))
    b = asyncio.run(service.create_subscription("tenant-b", "人工智能"))
    ingest = _Ingest(policies)

    async def valid_page(url: str) -> str:
        return "创新创业大赛报名正在进行，请及时参赛。"

    with patch.object(ContestService, "_fetch_and_validate", staticmethod(valid_page)):
        first = asyncio.run(service._search_subscription(a, ingest))
        second = asyncio.run(service._search_subscription(b, ingest))
        repeat = asyncio.run(service._search_subscription(a, ingest))

    assert len(policies) == 1
    assert first["tenant_new"] == 1
    assert second["tenant_new"] == 1
    assert repeat["tenant_new"] == 0
    assert notified == [
        ("tenant-a", ["https://example.test/contest-1"]),
        ("tenant-b", ["https://example.test/contest-1"]),
    ]


def test_discovery_uses_precise_query_and_skips_low_value_domains() -> None:
    contest, policies = _ContestRepo(), {}
    search = _Search()
    service = _service(contest, policies, search=search)
    sub = asyncio.run(service.create_subscription("tenant-a", "创新创业"))

    assert ContestService._is_discovery_candidate_url("https://www.youtube.com/watch?v=123") is False
    assert ContestService._is_discovery_candidate_url("https://www.bing.com/ck/a?u=target") is False
    assert ContestService._is_discovery_candidate_url("https://gxt.jiangsu.gov.cn/notice", {"gxt.jiangsu.gov.cn"}) is False
    assert ContestService._is_discovery_candidate_url("https://example.gov.cn/contest") is True
    assert ContestService._build_discovery_query("创新创业") == (
        '"创新创业" (比赛 OR 大赛 OR 竞赛 OR 挑战赛) '
        "(报名 OR 参赛 OR 征集 OR 申报) -获奖 -公示 -名单 -结果"
    )

    async def no_candidate(url: str) -> str:
        return ""

    with patch.object(ContestService, "_fetch_and_validate", staticmethod(no_candidate)):
        asyncio.run(service._search_subscription(sub, _Ingest(policies)))

    assert search.calls == [(ContestService._build_discovery_query("创新创业"), "past_month")]
