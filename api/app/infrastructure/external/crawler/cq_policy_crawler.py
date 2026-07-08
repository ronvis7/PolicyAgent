"""重庆市级门户政策/赛事爬虫(TRS WCM 通用)。

数据源逆向(2026-07-07)：kjj.cq.gov.cn(市科技局)与 jjxxw.cq.gov.cn(市经信委)同属
TRS WCM 静态站——列表为静态分页 index.html / index_1.html / ...，总页数在页内
`createPage(N, ...)` 调用；详情链接形如 202607/t20260702_15795188.html(路径自带日期)；
正文在 div.trs_editor_view(kjj 外层为 .zwxl-article)。两站列表条目模板略异
(kjj=li 内 a[title]+兄弟 span 日期 / jjxxw=a 内嵌 p 标题+span 日期)，一套解析兼容。

与 wnd/shyp/gxt 同属通用多区域框架：纯解析函数(_parse_list_page/_parse_detail)与
网络 I/O 分离便于单测；普通浏览器 UA + 限速、只取 HTML 正文不下载附件。
base_url/column_path 参数化，同一类注册多个市级委办局栏目来源。
"""

import asyncio
import logging
import re
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.policy import Policy
from app.infrastructure.external.crawler.list_filter import (
    filter_list_items,
    freshness_cutoff,
    page_all_stale,
)

logger = logging.getLogger(__name__)

_REGION = "重庆市"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_REQUEST_DELAY = 0.8  # 详情页之间的限速(秒)，对源站友好

# 详情链接：月目录/t{YYYYMMDD}_{id}.html(排除栏目导航等非详情链接)
_DETAIL_HREF_RE = re.compile(r"\d{6}/t\d{8}_\d+\.html$")
# 详情链接路径自带发布日期(与 gxt 的 URL 日期兜底同理)
_URL_DATE_RE = re.compile(r"/t(\d{4})(\d{2})(\d{2})_\d+\.html")
# 静态分页总页数：页内 createPage(N, 当前页, "index", "html") 调用(function 定义行无数字不误匹配)
_TOTAL_RE = re.compile(r"createPage\(\s*(\d+)")
# 真文号形态(如 渝科局发〔2026〕88号)，best-effort 提取(与 gxt 同规则)
_DOC_NUMBER_RE = re.compile(r"[一-龥A-Za-z]{2,20}[〔\[（]\d{4}[〕\]）]\s*第?\s*\d+\s*号")


def _parse_publish_date(raw: Optional[str]) -> Optional[date]:
    """将 'YYYY-MM-DD' 安全解析为 date，失败返回 None。"""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _date_from_url(url: str) -> Optional[date]:
    """从详情链接 /tYYYYMMDD_id.html 派生发布日期(TRS 命名约定，列表缺日期时兜底)。"""
    m = _URL_DATE_RE.search(url or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


class CqPolicyCrawler(PolicyCrawler):
    """重庆市级门户爬虫(httpx + BeautifulSoup，TRS WCM 静态分页)。

    base_url + column_path 定位栏目；`title_keyword` 仅保留标题命中的条目
    (赛事子源用"大赛")；max_age_days/title_exclude 为赛事保鲜过滤(见 list_filter)。
    """

    def __init__(
        self,
        base_url: str,
        column_path: str,
        source: str,
        region: str = _REGION,
        request_delay: float = _REQUEST_DELAY,
        title_keyword: Optional[str] = None,
        max_age_days: Optional[int] = None,
        title_exclude: Sequence[str] = (),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._column_path = column_path if column_path.endswith("/") else column_path + "/"
        self._source = source
        self._region = region
        self._request_delay = request_delay
        self._title_keyword = title_keyword
        # 赛事子源的列表级保鲜过滤(见 list_filter)：缺省(None/空)零行为变化。
        self._max_age_days = max_age_days
        self._title_exclude = title_exclude

    def _page_url(self, page: int) -> str:
        """TRS 静态分页：第1页 index.html，第 n 页 index_{n-1}.html。"""
        name = "index.html" if page <= 1 else f"index_{page - 1}.html"
        return f"{self._base_url}{self._column_path}{name}"

    @staticmethod
    def _parse_list_page(
        html: str, list_url: str, source: str, region: str,
    ) -> List[Policy]:
        """从列表页 HTML 解析结构化政策(不含正文，由详情页补全)。

        兼容两套条目模板：kjj=li 内 a[title 属性]+兄弟 span 日期；
        jjxxw=a 内嵌 p 标题+span 日期。日期文本取不到时从 URL 路径派生。
        """
        soup = BeautifulSoup(html or "", "html.parser")
        policies: List[Policy] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if not _DETAIL_HREF_RE.search(href):
                continue
            url = urljoin(list_url, href)
            p_el = anchor.find("p")
            title = (
                anchor.get("title")
                or (p_el.get_text(strip=True) if p_el else "")
                or anchor.get_text(strip=True)
            ).strip()
            if not title:
                continue
            date_el = anchor.find("span") or anchor.find_next_sibling("span")
            publish_date = (
                _parse_publish_date(date_el.get_text(strip=True) if date_el else "")
                or _date_from_url(url)
            )
            policies.append(Policy(
                source=source,
                source_url=url,
                title=title,
                publish_date=publish_date,
                region=region,
            ))
        return policies

    @staticmethod
    def _total_pages(html: str) -> int:
        """从页内 createPage(N, ...) 调用读取总页数，取不到返回 0。"""
        match = _TOTAL_RE.search(html or "")
        return int(match.group(1)) if match else 0

    @staticmethod
    def _parse_detail(html: str) -> Tuple[str, str]:
        """从详情页 HTML 解析(正文, 文号)。正文取 div.trs_editor_view(TRS 编辑器容器，
        两站通用)，回退 .zwxl-article / .pages_content；文号按真文号形态 best-effort。"""
        soup = BeautifulSoup(html or "", "html.parser")

        body_el = (
            soup.select_one(".trs_editor_view")
            or soup.select_one(".zwxl-article")
            or soup.select_one(".pages_content")
            or soup.select_one("#Zoom")
        )
        body_text = body_el.get_text("\n", strip=True) if body_el else ""

        match = _DOC_NUMBER_RE.search(soup.get_text(" ", strip=True))
        doc_number = match.group(0).strip() if match else ""
        return body_text, doc_number

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        """抓取最多 max_pages 页(含详情正文)，限速且对失败条目容错跳过。"""
        collected: List[Policy] = []
        cutoff = freshness_cutoff(self._max_age_days)
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA}, timeout=25, follow_redirects=True
        ) as client:
            for page in range(1, max_pages + 1):
                html = await self._fetch_page(client, page)
                if html is None:
                    break
                # 先按原始记录判"到底"，再做关键词过滤(与 gxt 同教训：
                # 低频词"大赛"常把整页滤空，滤空 ≠ 到底，须继续翻页)。
                raw_policies = self._parse_list_page(
                    html, self._page_url(page), self._source, self._region,
                )
                if not raw_policies:
                    break
                page_policies = (
                    [p for p in raw_policies if self._title_keyword in p.title]
                    if self._title_keyword
                    else raw_policies
                )
                page_policies = filter_list_items(page_policies, cutoff, self._title_exclude)
                for policy in page_policies:
                    await self._enrich_detail(client, policy)
                    collected.append(policy)
                    await asyncio.sleep(self._request_delay)
                # 列表按日期倒序：整页原始记录过旧说明后页只会更旧，提前收工
                if page_all_stale(raw_policies, cutoff):
                    break
                total = self._total_pages(html)
                if total and page >= total:
                    break
        logger.info(f"cq 政策爬虫({self._source})抓取完成，共 {len(collected)} 条")
        return collected

    async def _fetch_page(self, client: httpx.AsyncClient, page: int) -> Optional[str]:
        """抓取某页静态列表 HTML，失败返回 None。"""
        url = self._page_url(page)
        try:
            resp = await client.get(url, headers={"Referer": self._base_url})
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            logger.warning(f"cq 政策列表第 {page} 页抓取失败[{url}]: {type(e).__name__}: {e}")
            return None

    async def _enrich_detail(self, client: httpx.AsyncClient, policy: Policy) -> None:
        """抓取详情页补全正文与文号；失败保留列表已得字段，不中断整批。"""
        try:
            resp = await client.get(policy.source_url)
            resp.raise_for_status()
            body_text, doc_number = self._parse_detail(resp.text)
            policy.body_text = body_text
            policy.doc_number = doc_number
            policy.crawled_at = datetime.now()
        except httpx.HTTPError as e:
            logger.warning(f"政策详情页抓取失败[{policy.source_url}]: {type(e).__name__}: {e}")
