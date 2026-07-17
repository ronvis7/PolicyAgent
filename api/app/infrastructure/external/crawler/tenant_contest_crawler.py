"""Safe, deliberately small static HTML crawler for tenant-owned contest portals."""

import asyncio
import ipaddress
import socket
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.application.errors.exceptions import BadRequestError
from app.domain.models.contest import TenantContestSource
from app.domain.models.policy import Policy


MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 3
_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


async def assert_public_http_url(url: str) -> None:
    """Reject credentials and any DNS result that can reach local infrastructure."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise BadRequestError("只支持不含账号密码的公网 HTTP(S) 地址")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise BadRequestError("不允许访问本机或内网地址")
    try:
        addresses = await asyncio.get_running_loop().run_in_executor(
            None, lambda: socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM),
        )
    except socket.gaierror as exc:
        raise BadRequestError("网址无法解析") from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local or
                address.is_reserved or address.is_multicast or address.is_unspecified):
            raise BadRequestError("不允许访问内网地址")


class TenantContestCrawler:
    def __init__(self, source: TenantContestSource) -> None:
        self.source = source

    async def crawl(self, max_pages: int = 1) -> list[Policy]:
        await assert_public_http_url(self.source.list_url)
        list_html, list_url = await self._get_html(self.source.list_url)
        soup = BeautifulSoup(list_html, "html.parser")
        anchors = soup.select(self.source.link_selector)
        if not anchors:
            raise BadRequestError("列表链接 CSS 选择器没有匹配到任何链接")

        keywords = [value.strip() for value in self.source.title_keywords.replace("，", ",").split(",") if value.strip()]
        result: list[Policy] = []
        seen: set[str] = set()
        for anchor in anchors[:50]:
            href = anchor.get("href")
            title = anchor.get_text(" ", strip=True)
            if not href or not title or (keywords and not any(word in title for word in keywords)):
                continue
            detail_url = urljoin(list_url, href)
            if detail_url in seen:
                continue
            seen.add(detail_url)
            try:
                detail_html, resolved_url = await self._get_html(detail_url)
            except (httpx.HTTPError, BadRequestError):
                continue
            detail = BeautifulSoup(detail_html, "html.parser")
            content = detail.select_one(self.source.content_selector)
            if content is None:
                continue
            body = content.get_text("\n", strip=True)
            policy = Policy(
                source=f"tenant-source-{self.source.id}", source_url=resolved_url, title=title,
                body_text=body[:50_000], region=self.source.region, item_type="competition",
                origin_type="tenant", source_name=self.source.name, crawled_at=datetime.now(),
            )
            if not any(word in title for word in ("获奖", "公示", "名单", "结果")):
                result.append(policy)
        return result

    async def _get_html(self, url: str) -> tuple[str, str]:
        current = url
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await assert_public_http_url(current)
                response = await client.get(current, headers={"User-Agent": "PolicyManus tenant contest crawler/1.0"})
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise BadRequestError("重定向响应缺少目标地址")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "html" not in content_type:
                    raise BadRequestError("仅支持静态 HTML 页面，不支持 PDF、登录墙或动态接口")
                if len(response.content) > MAX_RESPONSE_BYTES:
                    raise BadRequestError("页面响应过大")
                return response.text, str(response.url)
        raise BadRequestError("重定向次数过多")
