"""上海市杨浦区门户政策爬虫。

数据源逆向(2026-06-17)：门户为东网(easttone)政务云 CMS。列表走同源 JSON 接口
POST /front/api/data/search(ES 后端)，body 传 channelList(数组)+pageNo+pageSize，
返回 data.list[](title/url/dispatch_agency/display_date 毫秒时间戳)与 data.totalPage；
详情页为服务端直出静态 HTML，正文在 div#ivs_content(class=Article_content)，
发文字号/索引号在「标签 span + 值 span」结构里。

与无锡(wnd)同属通用多区域框架的一个来源：纯解析函数(_parse_list_payload/_parse_detail)
与网络 I/O 分离便于单测；普通浏览器 UA + 限速、只取 HTML 正文不下载附件。
"""

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.policy import Policy

logger = logging.getLogger(__name__)

_BASE = "https://www.shyp.gov.cn"
_LIST_API = f"{_BASE}/front/api/data/search"
# 「政府文件」栏目 id(逆向自 /zhengwu/zwgk-zfwj/ 页面 CMS 配置 ids:'1899'；
# channelList 必须传数组，传字符串会被后端忽略而返回全站数据)
_CHANNEL_GOV_DOC = "1899"
_SOURCE = "shyp"
_REGION = "上海市杨浦区"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

_DEFAULT_PAGE_SIZE = 15
_REQUEST_DELAY = 0.8  # 详情页之间的限速(秒)，对源站友好
_DASH_CHARS = set("—-－ \xa0")  # 占位短横，视为空值


def _parse_publish_date_ms(raw: object) -> Optional[date]:
    """将毫秒级 epoch 时间戳(display_date)安全解析为 date，失败返回 None。"""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        ms = int(raw)
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def _clean_dash(value: str) -> str:
    """将纯占位短横(如 '—  —')规整为空字符串。"""
    cleaned = (value or "").replace("\xa0", " ").strip()
    return "" if all(ch in _DASH_CHARS for ch in cleaned) else cleaned


class ShypPolicyCrawler(PolicyCrawler):
    """上海杨浦区门户政策爬虫(httpx + BeautifulSoup)。

    列表走 ES 搜索接口按栏目 channelList 抓取；详情页静态 HTML 补全正文/文号/索引号。
    """

    def __init__(
        self,
        page_size: int = _DEFAULT_PAGE_SIZE,
        request_delay: float = _REQUEST_DELAY,
        channel: str = _CHANNEL_GOV_DOC,
        source: str = _SOURCE,
    ) -> None:
        self._page_size = page_size
        self._request_delay = request_delay
        self._channel = channel
        self._source = source

    @staticmethod
    def _parse_list_payload(payload: dict, source: str = _SOURCE) -> List[Policy]:
        """从列表接口 JSON 解析出结构化政策(不含正文/文号，由详情页补全)。"""
        data = (payload or {}).get("data") or {}
        rows = data.get("list") or []
        policies: List[Policy] = []
        for row in rows:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            policies.append(
                Policy(
                    source=source,
                    source_url=url,
                    title=(row.get("title") or "").strip(),
                    issuer=(row.get("dispatch_agency") or row.get("drafting_unit") or "").strip(),
                    publish_date=_parse_publish_date_ms(row.get("display_date")),
                    region=_REGION,
                )
            )
        return policies

    @staticmethod
    def _total_pages(payload: dict) -> int:
        """从列表接口 JSON 读取总页数。"""
        return int(((payload or {}).get("data") or {}).get("totalPage") or 0)

    @staticmethod
    def _meta_value(soup: BeautifulSoup, label: str) -> str:
        """从「<span>标签：</span><span>值</span>」结构里取标签对应的值。"""
        for span in soup.find_all("span"):
            text = span.get_text(strip=True)
            if text.startswith(label):
                sibling = span.find_next_sibling("span")
                if sibling:
                    return _clean_dash(sibling.get_text(strip=True))
        return ""

    @classmethod
    def _parse_detail(cls, html: str) -> Tuple[str, str, str]:
        """从详情页 HTML 解析(正文, 文号, 索引号)。

        正文取 div#ivs_content(class=Article_content)，文号取「发文字号」、索引号取「索引号」。
        """
        soup = BeautifulSoup(html or "", "html.parser")

        body_el = soup.select_one("#ivs_content") or soup.select_one(".Article_content")
        body_text = body_el.get_text("\n", strip=True) if body_el else ""

        doc_number = cls._meta_value(soup, "发文字号") or cls._meta_value(soup, "文号")
        index_number = cls._meta_value(soup, "索引号")
        return body_text, doc_number, index_number

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        """抓取最多 max_pages 页政策(含详情正文)，限速且对失败条目容错跳过。"""
        collected: List[Policy] = []
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA}, timeout=25, follow_redirects=True
        ) as client:
            for page in range(1, max_pages + 1):
                payload = await self._fetch_list(client, page)
                if payload is None:
                    break
                page_policies = self._parse_list_payload(payload, self._source)
                if not page_policies:
                    break
                for policy in page_policies:
                    await self._enrich_detail(client, policy)
                    collected.append(policy)
                    await asyncio.sleep(self._request_delay)
                if page >= self._total_pages(payload):
                    break
        logger.info(f"shyp 政策爬虫抓取完成，共 {len(collected)} 条")
        return collected

    async def _fetch_list(self, client: httpx.AsyncClient, page: int) -> Optional[dict]:
        """抓取某页列表 JSON，失败返回 None。channelList 必须为数组才生效。"""
        body = {
            "channelList": [self._channel],
            "pageNo": page,
            "pageSize": self._page_size,
            "orderFields": ["display_date", "id"],
            "orderTypes": ["desc", "desc"],
        }
        try:
            resp = await client.post(
                _LIST_API,
                json=body,
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": _BASE},
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"shyp 政策列表第 {page} 页抓取失败: {type(e).__name__}: {e}")
            return None

    async def _enrich_detail(self, client: httpx.AsyncClient, policy: Policy) -> None:
        """抓取详情页补全正文/文号/索引号；失败保留列表已得字段，不中断整批。"""
        try:
            resp = await client.get(policy.source_url)
            resp.raise_for_status()
            body_text, doc_number, index_number = self._parse_detail(resp.text)
            policy.body_text = body_text
            policy.doc_number = doc_number
            if index_number:
                policy.index_number = index_number
            policy.crawled_at = datetime.now()
        except httpx.HTTPError as e:
            logger.warning(f"政策详情页抓取失败[{policy.source_url}]: {type(e).__name__}: {e}")
