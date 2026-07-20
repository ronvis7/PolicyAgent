import logging
from typing import Any, Optional

import httpx

from app.domain.external.search import SearchEngine
from app.domain.models.search import SearchResultItem, SearchResults
from app.domain.models.tool_result import ToolResult

logger = logging.getLogger(__name__)

_RECENCY_FILTERS = {
    "past_hour": "week",
    "past_day": "week",
    "past_week": "week",
    "past_month": "month",
    "past_year": "year",
}


class BaiduSearchEngine(SearchEngine):
    """百度千帆 v2 网页搜索适配器。"""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://qianfan.baidubce.com/v2/ai_search/web_search",
        top_k: int = 20,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url
        self.top_k = max(1, min(top_k, 50))

    async def invoke(self, query: str, date_range: Optional[str] = None) -> ToolResult[SearchResults]:
        if not self.api_key:
            return self._failure(query, date_range, "百度搜索 API Key 未配置")

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._build_payload(query, date_range),
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("百度搜索请求失败: %s", exc)
            return self._failure(query, date_range, f"百度搜索请求失败: {type(exc).__name__}")

        if payload.get("code") not in (None, "", 0, "0") and not payload.get("references"):
            message = str(payload.get("message") or payload.get("code") or "未知错误")
            return self._failure(query, date_range, f"百度搜索返回错误: {message}")

        results = self._parse_results(payload)
        return ToolResult(success=True, data=SearchResults(
            query=query,
            date_range=date_range,
            total_results=len(results),
            results=results,
        ))

    def _build_payload(self, query: str, date_range: Optional[str]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": self.top_k}],
        }
        if recency := _RECENCY_FILTERS.get(date_range or ""):
            payload["search_recency_filter"] = recency
        return payload

    @staticmethod
    def _parse_results(payload: dict[str, Any]) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        seen_urls: set[str] = set()
        for reference in payload.get("references") or []:
            url = str(reference.get("url") or reference.get("link") or "").strip()
            title = str(reference.get("title") or "").strip()
            if not url.startswith(("http://", "https://")) or not title or url in seen_urls:
                continue
            seen_urls.add(url)
            snippet = str(
                reference.get("content")
                or reference.get("snippet")
                or reference.get("summary")
                or ""
            ).strip()
            results.append(SearchResultItem(title=title, url=url, snippet=snippet))
        return results

    @staticmethod
    def _failure(query: str, date_range: Optional[str], message: str) -> ToolResult[SearchResults]:
        return ToolResult(
            success=False,
            message=message,
            data=SearchResults(query=query, date_range=date_range, total_results=0, results=[]),
        )
