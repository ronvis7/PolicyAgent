"""赛事中心：可信官方源、租户关键词订阅与全网发现。"""

import ipaddress
import re
from datetime import datetime
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.application.errors.exceptions import BadRequestError, ConflictError, NotFoundError
from app.application.services.policy_ingest_service import PolicyIngestService
from app.domain.external.search import SearchEngine
from app.domain.models.contest import ContestDiscoveryHit, ContestSource, ContestSubscription
from app.domain.models.policy import Policy
from app.domain.repositories.uow import IUnitOfWork
from app.infrastructure.external.crawler.contest_source_factory import SUPPORTED_CONTEST_ADAPTERS, build_contest_crawler

_INCLUDE = re.compile(r"比赛|大赛|竞赛|挑战赛|创业赛")
_REGISTRATION = re.compile(r"报名|参赛|征集|申报")
_EXCLUDE = re.compile(r"获奖|公示|公布|名单|结果")


class ContestService:
    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        search_engine: SearchEngine,
        on_tenant_discovered: Optional[Callable[[str, List[Policy]], Awaitable[None]]] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._search_engine = search_engine
        self._on_tenant_discovered = on_tenant_discovered

    async def list_contests(self, **filters) -> Tuple[List[Policy], int]:
        async with self._uow_factory() as uow:
            return await uow.policy.list_contests(**filters)

    async def get_contest(self, contest_id: str) -> Policy:
        async with self._uow_factory() as uow:
            policy = await uow.policy.get_by_id(contest_id)
        if policy is None or policy.item_type != "competition":
            raise NotFoundError("赛事不存在")
        return policy

    async def list_sources(self, enabled_only: bool = False) -> List[ContestSource]:
        async with self._uow_factory() as uow:
            return await uow.contest.list_sources(enabled_only)

    async def save_source(self, source: ContestSource) -> ContestSource:
        source.key = source.key.strip().lower().replace(" ", "-")
        if not source.key or not re.fullmatch(r"[a-z0-9-]{2,64}", source.key):
            raise BadRequestError("来源 key 只能使用小写字母、数字和连字符")
        if source.adapter_type not in SUPPORTED_CONTEST_ADAPTERS:
            raise BadRequestError("请选择平台已验证的赛事爬虫模板")
        build_contest_crawler(source)  # 配置完整性校验，不发网络请求
        async with self._uow_factory() as uow:
            existing = await uow.contest.get_source_by_key(source.key)
            if existing and existing.id != source.id:
                raise ConflictError("赛事来源 key 已存在")
            await uow.contest.save_source(source)
        return source

    async def update_source(self, source_id: str, **changes) -> ContestSource:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_source(source_id)
        if source is None:
            raise NotFoundError("赛事来源不存在")
        updated = source.model_copy(update={**changes, "updated_at": datetime.now()})
        return await self.save_source(updated)

    async def delete_source(self, source_id: str) -> None:
        async with self._uow_factory() as uow:
            if not await uow.contest.delete_source(source_id):
                raise NotFoundError("赛事来源不存在")

    async def preflight_source(self, source_id: str) -> dict:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_source(source_id)
        if source is None:
            raise NotFoundError("赛事来源不存在")
        rows = await build_contest_crawler(source).crawl(max_pages=1)
        return {"source_id": source.id, "source": source.name, "sample_count": len(rows)}

    async def ingest_source(self, source_id: str, ingest_service: PolicyIngestService) -> dict:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_source(source_id)
        if source is None:
            raise NotFoundError("赛事来源不存在")
        if not source.enabled:
            raise BadRequestError("该赛事来源已停用")
        return await ingest_service.ingest_with_crawler(source.key, build_contest_crawler(source), source.name)

    async def list_subscriptions(self, tenant_id: str) -> List[ContestSubscription]:
        async with self._uow_factory() as uow:
            return await uow.contest.list_subscriptions(tenant_id)

    async def create_subscription(self, tenant_id: str, keyword: str) -> ContestSubscription:
        keyword = keyword.strip()
        if not keyword:
            raise BadRequestError("关键词不能为空")
        async with self._uow_factory() as uow:
            if await uow.contest.get_subscription_by_keyword(tenant_id, keyword):
                raise ConflictError("该关键词已订阅")
            subscription = ContestSubscription(tenant_id=tenant_id, keyword=keyword)
            await uow.contest.save_subscription(subscription)
        return subscription

    async def update_subscription(self, tenant_id: str, subscription_id: str, enabled: bool) -> ContestSubscription:
        async with self._uow_factory() as uow:
            current = await uow.contest.get_subscription(tenant_id, subscription_id)
            if current is None:
                raise NotFoundError("关键词订阅不存在")
            updated = current.model_copy(update={"enabled": enabled, "updated_at": datetime.now()})
            await uow.contest.save_subscription(updated)
        return updated

    async def delete_subscription(self, tenant_id: str, subscription_id: str) -> None:
        async with self._uow_factory() as uow:
            if not await uow.contest.delete_subscription(tenant_id, subscription_id):
                raise NotFoundError("关键词订阅不存在")

    async def discover_all(self, ingest_service: PolicyIngestService) -> List[dict]:
        """每日全网发现；一次失败不影响其他企业关键词。"""
        async with self._uow_factory() as uow:
            subscriptions = await uow.contest.list_enabled_subscriptions()
        summaries: List[dict] = []
        for sub in subscriptions:
            try:
                result = await self._search_subscription(sub, ingest_service)
                summaries.append(result)
            except Exception as exc:  # best-effort
                summaries.append({"tenant_id": sub.tenant_id, "keyword": sub.keyword, "error": type(exc).__name__})
        return summaries

    async def _search_subscription(self, subscription: ContestSubscription, ingest_service: PolicyIngestService) -> dict:
        search = await self._search_engine.invoke(f"{subscription.keyword} 比赛 大赛 报名", "past_month")
        candidates: List[Policy] = []
        if search.success and search.data:
            for row in search.data.results[:10]:
                body = await self._fetch_and_validate(row.url)
                text = f"{row.title}\n{row.snippet}\n{body}"
                if body and _INCLUDE.search(text) and _REGISTRATION.search(text) and not _EXCLUDE.search(text):
                    candidates.append(Policy(source="web-discovery", source_url=row.url, title=row.title,
                                             body_text=body, region="全国", item_type="competition",
                                             origin_type="web", source_name="全网发现"))
        if candidates:
            class _ResultCrawler:
                async def crawl(self, max_pages: int = 1):
                    return candidates
            summary = await ingest_service.ingest_with_crawler("web-discovery", _ResultCrawler(), "全网发现", origin_type="web")
        else:
            summary = {"source": "web-discovery", "crawled": 0, "new": 0}
        notify: List[Policy] = []
        async with self._uow_factory() as uow:
            current = await uow.contest.get_subscription(subscription.tenant_id, subscription.id)
            if current:
                await uow.contest.save_subscription(current.model_copy(update={"last_run_at": datetime.now()}))
            for candidate in candidates:
                policy = await uow.policy.get_by_source_url(candidate.source_url)
                if policy is None or await uow.contest.has_discovery_hit(subscription.tenant_id, policy.id):
                    continue
                await uow.contest.save_discovery_hit(ContestDiscoveryHit(
                    tenant_id=subscription.tenant_id,
                    subscription_id=subscription.id,
                    policy_id=policy.id,
                ))
                notify.append(policy)
        if notify and self._on_tenant_discovered is not None:
            await self._on_tenant_discovered(subscription.tenant_id, notify)
        return {**summary, "tenant_id": subscription.tenant_id, "keyword": subscription.keyword, "tenant_new": len(notify)}

    @staticmethod
    async def _fetch_and_validate(url: str) -> str:
        if not ContestService._is_public_http_url(url):
            return ""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "PolicyManus contest discovery/1.0"})
                response.raise_for_status()
            if not ContestService._is_public_http_url(str(response.url)):
                return ""
            soup = BeautifulSoup(response.text, "html.parser")
            return soup.get_text("\n", strip=True)[:20000]
        except httpx.HTTPError:
            return ""

    @staticmethod
    def _is_public_http_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return False
        hostname = parsed.hostname.lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return False
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return True
        return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)
