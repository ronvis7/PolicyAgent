"""无锡高新区(新吴区)门户政策爬虫。

数据源逆向(2026-06-14)：列表走 JSON 接口 POST /info_open/search(siteId=181 +
政策文件栏目 channelIds)，详情页 HTML 取正文(div#Zoom)与文号(table.xxgk_table_wza)。
robots 仅全禁 GPTBot、禁索引 /uploadfiles/ 附件 → 用普通浏览器 UA + 限速爬 HTML，
不下载二进制附件。纯解析函数(_parse_list_payload/_parse_detail)与网络 I/O 分离，便于单测。
"""

import asyncio
import logging
from datetime import date, datetime
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.policy import Policy

logger = logging.getLogger(__name__)

_BASE = "https://www.wnd.gov.cn"
_LIST_API = f"{_BASE}/info_open/search"
_SITE_ID = 181
# 政策文件栏目集(从列表页 chanIdStr 逆向)
_CHANNEL_IDS = "38939,38940,38941,62112,62113,62114"
_SOURCE = "wnd"
_REGION = "江苏省无锡市新吴区"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

_DEFAULT_PAGE_SIZE = 20
_REQUEST_DELAY = 0.8  # 详情页之间的限速(秒)，对源站友好
_DASH_CHARS = set("—-－ \xa0")  # 占位短横，视为空值


def _parse_publish_date(raw: Optional[str]) -> Optional[date]:
    """将 'YYYY-MM-DD' 安全解析为 date，失败返回 None"""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _clean_dash(value: str) -> str:
    """将纯占位短横(如 '—  —')规整为空字符串"""
    cleaned = (value or "").replace("\xa0", " ").strip()
    return "" if all(ch in _DASH_CHARS for ch in cleaned) else cleaned


class WndPolicyCrawler(PolicyCrawler):
    """无锡新吴区门户政策爬虫(httpx + BeautifulSoup)。

    两种抓取模式(同一 /info_open/search 接口)：
    - 默认(title_keyword=None)：按「政策文件」栏目 channelIds 抓规范性文件(主线②原行为)；
    - 申报模式(title_keyword='申报')：按标题关键词全站检索项目/资金申报通知——这类通知才
      含申报截止日期(供主线⑤抽取)。channelIds 与 title 关键词二选一驱动列表接口。
    """

    def __init__(
        self,
        page_size: int = _DEFAULT_PAGE_SIZE,
        request_delay: float = _REQUEST_DELAY,
        title_keyword: Optional[str] = None,
        source: str = _SOURCE,
    ) -> None:
        self._page_size = page_size
        self._request_delay = request_delay
        self._title_keyword = title_keyword
        self._source = source

    @staticmethod
    def _parse_list_payload(payload: dict, source: str = _SOURCE) -> List[Policy]:
        """从列表接口 JSON 解析出结构化政策(不含正文/文号，由详情页补全)"""
        data = (payload or {}).get("data") or {}
        rows = data.get("data") or []
        policies: List[Policy] = []
        for row in rows:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            policies.append(
                Policy(
                    source=source,
                    source_url=url,
                    index_number=(row.get("indexId") or "").strip(),
                    title=(row.get("title") or "").strip(),
                    issuer=(row.get("organization") or "").strip(),
                    status=(row.get("effectStatus") or "").strip(),
                    publish_date=_parse_publish_date(row.get("writeTime") or row.get("openTime")),
                    region=_REGION,
                )
            )
        return policies

    @staticmethod
    def _total_pages(payload: dict) -> int:
        """从列表接口 JSON 读取总页数"""
        return int(((payload or {}).get("data") or {}).get("totalPages") or 0)

    @staticmethod
    def _parse_detail(html: str) -> Tuple[str, str]:
        """从详情页 HTML 解析(正文, 文号)。正文取 div#Zoom，文号取元数据表'文件编号'。"""
        soup = BeautifulSoup(html or "", "html.parser")

        body_el = soup.select_one("#Zoom") or soup.select_one("div.doc_content_wza")
        body_text = body_el.get_text("\n", strip=True) if body_el else ""

        doc_number = ""
        table = soup.select_one("table.xxgk_table_wza")
        if table:
            cells = [c.get_text(strip=True) for c in table.find_all(["th", "td"])]
            for key, value in zip(cells[::2], cells[1::2]):
                if key in ("文件编号", "发文字号", "文号"):
                    doc_number = _clean_dash(value)
                    break
        return body_text, doc_number

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        """抓取最多 max_pages 页政策(含详情正文)，限速且对失败条目容错跳过"""
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
        logger.info(f"wnd 政策爬虫抓取完成，共 {len(collected)} 条")
        return collected

    async def _fetch_list(self, client: httpx.AsyncClient, page: int) -> Optional[dict]:
        """抓取某页列表 JSON，失败返回 None。

        申报模式按 title 关键词全站检索(逆向确认 title 字段才真正过滤标题)；
        默认模式按政策文件栏目 channelIds 检索。
        """
        data = {
            "pageIndex": page,
            "pageSize": self._page_size,
            "siteId": _SITE_ID,
            "searchType": 2,
            "order": "writeTime",
        }
        if self._title_keyword:
            data["title"] = self._title_keyword
        else:
            data["channelIds"] = _CHANNEL_IDS
        try:
            resp = await client.post(
                _LIST_API,
                data=data,
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": _BASE},
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(f"wnd 政策列表第 {page} 页抓取失败: {type(e).__name__}: {e}")
            return None

    async def _enrich_detail(self, client: httpx.AsyncClient, policy: Policy) -> None:
        """抓取详情页补全正文与文号；失败保留列表已得字段，不中断整批"""
        try:
            resp = await client.get(policy.source_url)
            resp.raise_for_status()
            body_text, doc_number = self._parse_detail(resp.text)
            policy.body_text = body_text
            policy.doc_number = doc_number
            policy.crawled_at = datetime.now()
        except httpx.HTTPError as e:
            logger.warning(f"政策详情页抓取失败[{policy.source_url}]: {type(e).__name__}: {e}")
