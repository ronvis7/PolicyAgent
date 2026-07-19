"""赛事中心：可信官方源、租户关键词订阅与全网发现。"""

import ipaddress
import re
from datetime import datetime, timedelta
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.application.errors.exceptions import BadRequestError, ConflictError, NotFoundError
from app.application.services.policy_ingest_service import PolicyIngestService
from app.domain.external.search import SearchEngine
from app.domain.models.contest import ContestDiscoveryHit, ContestRun, ContestSource, ContestSubscription, TenantContestSource
from app.domain.models.policy import Policy
from app.domain.models.feed_item import FeedItem, FeedItemType
from app.domain.repositories.uow import IUnitOfWork
from app.infrastructure.external.crawler.contest_source_factory import SUPPORTED_CONTEST_ADAPTERS, build_contest_crawler
from app.infrastructure.external.crawler.tenant_contest_crawler import TenantContestCrawler, assert_public_http_url

_INCLUDE = re.compile(r"比赛|大赛|竞赛|挑战赛|创业赛")
_REGISTRATION = re.compile(r"报名|参赛|征集|申报")
_EXCLUDE = re.compile(r"获奖|公示|公布|名单|结果")
_DISCOVERY_BLOCKED_HOSTS = {
    "bing.com", "google.com", "youtube.com", "youtu.be", "play.google.com", "apps.apple.com",
}


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

    async def list_contests(self, tenant_id: str = "", **filters) -> Tuple[List[Policy], int]:
        async with self._uow_factory() as uow:
            items, total = await uow.policy.list_contests(tenant_id=tenant_id, **filters)
        official_hosts = await self._official_source_hosts()
        visible = [item for item in items if not (
            item.origin_type == "web" and any(
                (host := (urlparse(item.source_url).hostname or "").lower()) == official or host.endswith(f".{official}")
                for official in official_hosts
            )
        )]
        return visible, total - (len(items) - len(visible))

    async def get_contest(self, contest_id: str, tenant_id: str = "") -> Policy:
        async with self._uow_factory() as uow:
            policy = await uow.policy.get_by_id(contest_id)
            can_view_private = bool(tenant_id and policy and await uow.contest.tenant_can_view_policy(tenant_id, contest_id))
        if policy is None or policy.item_type != "competition" or (policy.origin_type == "tenant" and not can_view_private):
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
                run = ContestRun(tenant_id=sub.tenant_id, kind="discovery", target_id=sub.id, trigger="scheduled")
                async with self._uow_factory() as uow:
                    await uow.contest.save_run(run)
                result = await self.execute_discovery(sub.tenant_id, sub.id, run.id, ingest_service, "scheduled")
                summaries.append(result)
            except Exception as exc:  # best-effort
                summaries.append({"tenant_id": sub.tenant_id, "keyword": sub.keyword, "error": type(exc).__name__})
        return summaries

    async def _search_subscription(self, subscription: ContestSubscription, ingest_service: PolicyIngestService, notify: bool = True) -> dict:
        search = await self._search_engine.invoke(self._build_discovery_query(subscription.keyword), "past_month")
        official_hosts = await self._official_source_hosts()
        candidates: List[Policy] = []
        if search.success and search.data:
            for row in search.data.results[:10]:
                if not self._is_discovery_candidate_url(row.url, official_hosts):
                    continue
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
        notification_policies: List[Policy] = []
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
                notification_policies.append(policy)
        if notify and notification_policies and self._on_tenant_discovered is not None:
            await self._on_tenant_discovered(subscription.tenant_id, notification_policies)
        return {**summary, "tenant_id": subscription.tenant_id, "keyword": subscription.keyword,
                "tenant_new": len(notification_policies), "searched": len(search.data.results) if search.success and search.data else 0,
                "valid": len(candidates)}

    async def list_subscription_runs(self, tenant_id: str, subscription_id: str) -> List[ContestRun]:
        async with self._uow_factory() as uow:
            if not await uow.contest.get_subscription(tenant_id, subscription_id):
                raise NotFoundError("subscription not found")
            return await uow.contest.list_runs(tenant_id, "discovery", subscription_id)

    async def start_discovery(self, tenant_id: str, subscription_id: str) -> ContestRun:
        async with self._uow_factory() as uow:
            subscription = await uow.contest.get_subscription(tenant_id, subscription_id)
            if subscription is None:
                raise NotFoundError("subscription not found")
            if subscription.last_run_at and subscription.last_run_at > datetime.now() - timedelta(minutes=5):
                raise ConflictError("请在 5 分钟冷却后再次搜索")
            run = ContestRun(tenant_id=tenant_id, kind="discovery", target_id=subscription_id)
            await uow.contest.save_run(run)
        return run

    async def execute_discovery(self, tenant_id: str, subscription_id: str, run_id: str, ingest_service: PolicyIngestService, trigger: str = "manual") -> dict:
        async with self._uow_factory() as uow:
            subscription = await uow.contest.get_subscription(tenant_id, subscription_id)
        if subscription is None:
            raise NotFoundError("subscription not found")
        try:
            result = await self._search_subscription(subscription, ingest_service, notify=trigger == "scheduled")
            run = ContestRun(id=run_id, tenant_id=tenant_id, kind="discovery", target_id=subscription_id,
                trigger=trigger, status="succeeded", finished_at=datetime.now(),
                searched_count=int(result.get("searched", 0)), valid_count=int(result.get("valid", 0)),
                stored_count=int(result.get("new", 0)), feed_new_count=int(result.get("tenant_new", 0)))
        except Exception as exc:
            run = ContestRun(id=run_id, tenant_id=tenant_id, kind="discovery", target_id=subscription_id,
                trigger=trigger, status="failed", finished_at=datetime.now(), error_message=str(exc)[:1000])
            async with self._uow_factory() as uow:
                await uow.contest.save_run(run)
            raise
        async with self._uow_factory() as uow:
            await uow.contest.save_run(run)
        return result

    async def list_tenant_sources(self, tenant_id: str) -> List[TenantContestSource]:
        async with self._uow_factory() as uow:
            return await uow.contest.list_tenant_sources(tenant_id)

    async def suggest_tenant_sources(self, tenant_id: str, region: str) -> List[dict]:
        """Find public government portals first, then likely contest pages under them."""
        normalized = region.strip()
        if not normalized:
            raise BadRequestError("地区不能为空")
        existing_hosts = await self._official_source_hosts()
        suggestions: List[dict] = []
        seen_hosts: set[str] = set()
        queries = (
            # Portal home pages are evergreen, so this query deliberately has no date filter.
            f'"{normalized}" (科技委员会 OR 科技局 OR 工信局 OR 经信委 OR 人民政府) site:gov.cn',
            f'"{normalized}" (创新创业大赛 OR 创客中国 OR 科技创新大赛 OR 赛事通知) site:gov.cn',
        )
        for query in queries:
            search = await self._search_engine.invoke(query)
            if not search.success or not search.data:
                continue
            for item in search.data.results[:10]:
                if not self._is_public_http_url(item.url):
                    continue
                host = (urlparse(item.url).hostname or "").lower()
                if not host or host in seen_hosts or not host.endswith(".gov.cn"):
                    continue
                seen_hosts.add(host)
                title = f"{item.title} {item.snippet}"
                is_contest_page = bool(_INCLUDE.search(title))
                suggestions.append({
                    "name": f"{normalized} · {host}", "region": normalized, "list_url": item.url,
                    "reason": (
                        "已定位到公开政府赛事/通知页面；预检会继续验证静态列表与正文选择器。"
                        if is_contest_page else
                        "已定位到公开政府门户；预检会确认该页面是否含可抓取的赛事栏目。"
                    ) if host not in existing_hosts else "该域名已是平台官方来源，可直接选择上方地区预设。",
                })
                if len(suggestions) == 3:
                    return suggestions
        return suggestions

    async def create_tenant_source(self, tenant_id: str, source: TenantContestSource) -> TenantContestSource:
        source.tenant_id = tenant_id
        if source.preset_source_id:
            async with self._uow_factory() as uow:
                preset = await uow.contest.get_source(source.preset_source_id)
            if preset is None:
                raise BadRequestError("所选官方地区来源不存在")
            source = source.model_copy(update={
                "name": source.name.strip() or preset.name,
                "region": source.region.strip() or preset.region,
                "list_url": preset.home_url,
                "link_selector": "a",
                "content_selector": "body",
            })
        await self._validate_tenant_source(source)
        async with self._uow_factory() as uow:
            await uow.contest.save_tenant_source(source)
        return source

    async def update_tenant_source(self, tenant_id: str, source_id: str, **changes) -> TenantContestSource:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_tenant_source(tenant_id, source_id)
        if source is None:
            raise NotFoundError("tenant contest source not found")
        if changes.get("enabled") and source.preflight_at is None:
            raise BadRequestError("请先通过预检后再启用")
        updated = source.model_copy(update={**changes, "updated_at": datetime.now()})
        await self._validate_tenant_source(updated)
        async with self._uow_factory() as uow:
            await uow.contest.save_tenant_source(updated)
        return updated

    async def delete_tenant_source(self, tenant_id: str, source_id: str) -> None:
        async with self._uow_factory() as uow:
            if not await uow.contest.delete_tenant_source(tenant_id, source_id):
                raise NotFoundError("tenant contest source not found")

    async def preflight_tenant_source(self, tenant_id: str, source_id: str) -> dict:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_tenant_source(tenant_id, source_id)
        if source is None:
            raise NotFoundError("tenant contest source not found")
        rows = await self._tenant_source_crawler(source).crawl()
        updated = source.model_copy(update={"preflight_at": datetime.now(), "updated_at": datetime.now()})
        async with self._uow_factory() as uow:
            await uow.contest.save_tenant_source(updated)
        return {"source_id": source.id, "sample_count": len(rows), "sample_titles": [row.title for row in rows[:3]]}

    async def start_tenant_source_ingest(self, tenant_id: str, source_id: str) -> ContestRun:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_tenant_source(tenant_id, source_id)
            if source is None:
                raise NotFoundError("tenant contest source not found")
            if not source.enabled or source.preflight_at is None:
                raise BadRequestError("来源必须预检通过并启用")
            runs = await uow.contest.list_runs(tenant_id, "source", source_id, limit=1)
            if runs and runs[0].started_at > datetime.now() - timedelta(minutes=5):
                raise ConflictError("请在 5 分钟冷却后再次抓取")
            run = ContestRun(tenant_id=tenant_id, kind="source", target_id=source_id)
            await uow.contest.save_run(run)
        return run

    async def execute_tenant_source_ingest(self, tenant_id: str, source_id: str, run_id: str, ingest_service: PolicyIngestService, trigger: str = "manual") -> dict:
        async with self._uow_factory() as uow:
            source = await uow.contest.get_tenant_source(tenant_id, source_id)
        if source is None:
            raise NotFoundError("tenant contest source not found")
        try:
            rows = await self._tenant_source_crawler(source).crawl()
            class _Crawler:
                async def crawl(self, max_pages: int = 1): return rows
            ingest_key, ingest_name, origin_type, index = f"tenant-source-{source.id}", source.name, "tenant", False
            if source.preset_source_id:
                async with self._uow_factory() as uow:
                    preset = await uow.contest.get_source(source.preset_source_id)
                if preset is None:
                    raise NotFoundError("官方地区来源不存在")
                ingest_key, ingest_name, origin_type, index = preset.key, preset.name, "official", True
            summary = await ingest_service.ingest_with_crawler(ingest_key, _Crawler(), ingest_name, origin_type=origin_type, index=index)
            feed_new_count = 0
            async with self._uow_factory() as uow:
                for row in rows:
                    policy = await uow.policy.get_by_source_url(row.source_url)
                    if policy:
                        await uow.contest.link_tenant_source_policy(tenant_id, source.id, policy.id)
                        if trigger == "scheduled" and int(summary.get("new", 0)):
                            existing = await uow.feed.get_by_tenant_and_policy(tenant_id, policy.id)
                            if existing is None:
                                await uow.feed.save(FeedItem(
                                    tenant_id=tenant_id, type=FeedItemType.COMPETITION, policy_id=policy.id,
                                    title=policy.title, issuer=policy.issuer, publish_date=policy.publish_date,
                                    source_url=policy.source_url, region=policy.region,
                                    apply_deadline=policy.apply_deadline, deadline_status=policy.deadline_status,
                                ))
                                feed_new_count += 1
            run = ContestRun(id=run_id, tenant_id=tenant_id, kind="source", target_id=source_id, trigger=trigger,
                status="succeeded", finished_at=datetime.now(), searched_count=len(rows), valid_count=len(rows),
                stored_count=int(summary.get("new", 0)), feed_new_count=feed_new_count)
        except Exception as exc:
            run = ContestRun(id=run_id, tenant_id=tenant_id, kind="source", target_id=source_id, trigger=trigger,
                status="failed", finished_at=datetime.now(), error_message=str(exc)[:1000])
            async with self._uow_factory() as uow: await uow.contest.save_run(run)
            raise
        async with self._uow_factory() as uow: await uow.contest.save_run(run)
        return summary

    async def list_tenant_source_runs(self, tenant_id: str, source_id: str) -> List[ContestRun]:
        async with self._uow_factory() as uow:
            if not await uow.contest.get_tenant_source(tenant_id, source_id):
                raise NotFoundError("tenant contest source not found")
            return await uow.contest.list_runs(tenant_id, "source", source_id)

    async def ingest_all_tenant_sources(self, ingest_service: PolicyIngestService) -> List[dict]:
        async with self._uow_factory() as uow:
            sources = [source for source in await uow.contest.list_enabled_tenant_sources() if not source.preset_source_id]
        results: List[dict] = []
        for source in sources:
            run = ContestRun(tenant_id=source.tenant_id, kind="source", target_id=source.id, trigger="scheduled")
            async with self._uow_factory() as uow:
                await uow.contest.save_run(run)
            try:
                results.append(await self.execute_tenant_source_ingest(source.tenant_id, source.id, run.id, ingest_service, "scheduled"))
            except Exception as exc:
                results.append({"source_id": source.id, "error": type(exc).__name__})
        return results

    async def _validate_tenant_source(self, source: TenantContestSource) -> None:
        if not all((source.name.strip(), source.region.strip(), source.link_selector.strip(), source.content_selector.strip())):
            raise BadRequestError("名称、地区和 CSS 选择器不能为空")
        await assert_public_http_url(source.list_url)

    async def _tenant_source_crawler(self, source: TenantContestSource):
        if not source.preset_source_id:
            return TenantContestCrawler(source)
        async with self._uow_factory() as uow:
            preset = await uow.contest.get_source(source.preset_source_id)
        if preset is None:
            raise NotFoundError("官方地区来源不存在")
        return build_contest_crawler(preset)

    async def _official_source_hosts(self) -> set[str]:
        """Official portals are crawled in their own pipeline, never as web-discovery hits."""
        async with self._uow_factory() as uow:
            sources = await uow.contest.list_sources(enabled_only=True)
        return {host for source in sources if (host := (urlparse(source.home_url).hostname or "").lower())}

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
    def _build_discovery_query(keyword: str) -> str:
        """为中文关键词构建搜索查询。

        Bing 中文分词容易把"人工智能"拆成"人工"+单字，返回词典/百科类噪音。
        因此①不加引号(Bing 中文引号不生效) ②加 site:gov.cn 限政府网站
        ③竞争类关键词语义已足够收窄(比赛/大赛/报名等)，不需额外 + 号。
        """
        return (
            f"{keyword} (比赛 OR 大赛 OR 竞赛 OR 挑战赛) "
            "(报名 OR 参赛 OR 征集 OR 申报) site:gov.cn -获奖 -公示 -名单 -结果"
        )

    @classmethod
    def _is_discovery_candidate_url(cls, url: str, official_hosts: Optional[set[str]] = None) -> bool:
        if not cls._is_public_http_url(url):
            return False
        hostname = (urlparse(url).hostname or "").lower()
        blocked_hosts = _DISCOVERY_BLOCKED_HOSTS | (official_hosts or set())
        return not any(hostname == blocked or hostname.endswith(f".{blocked}") for blocked in blocked_hosts)

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
