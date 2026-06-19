"""江苏省工业和信息化厅门户政策爬虫。

数据源逆向(2026-06-19)：门户为大汉版通(Hanweb)CMS。列表走通用 AJAX 接口
GET /module/web/jpage/dataproxy.jsp(columnid/webid/unitid/appid/col 定位栏目，
startrecord/endrecord/perpage 翻页)，返回 XML：<totalrecord>N</totalrecord> +
若干 <record><![CDATA[ <li><a href title>标题</a><span>YYYY-MM-DD</span></li> ]]>；
详情页为服务端静态 HTML，正文在 div.article_zoom(回退 .nscont / #con1)。

「文件通知」栏目(columnid=6278)即省级项目/资金申报通知主阵地(创新型中小企业评价、
专精特新、制造业等)，供主线⑤申报截止抽取与③匹配。与 wnd/shyp 同属通用多区域框架：
纯解析函数(_parse_list_payload/_parse_detail)与网络 I/O 分离便于单测；普通浏览器 UA +
限速、只取 HTML 正文不下载附件。
"""

import asyncio
import logging
import math
import re
from datetime import date, datetime
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.policy import Policy

logger = logging.getLogger(__name__)

_BASE = "https://gxt.jiangsu.gov.cn"
_LIST_API = f"{_BASE}/module/web/jpage/dataproxy.jsp"
# 「文件通知」栏目定位参数(逆向自 col6278 列表页 jpage 初始化的 ajaxParam)
_COLUMN_ID = 6278
_WEB_ID = 23
_UNIT_ID = "403981"
_WEBNAME = "江苏省工业和信息化厅"
_SOURCE = "gxt"
_REGION = "江苏省"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

_DEFAULT_PAGE_SIZE = 15
_REQUEST_DELAY = 0.8  # 详情页之间的限速(秒)，对源站友好
_DASH_CHARS = set("—-－ \xa0")  # 占位短横，视为空值
# dataproxy 返回的每条记录是包在 <record><![CDATA[...]]></record> 里的 HTML 片段
_RECORD_RE = re.compile(r"<record>\s*<!\[CDATA\[(.*?)\]\]>\s*</record>", re.S)
_TOTAL_RE = re.compile(r"<totalrecord>\s*(\d+)\s*</totalrecord>", re.I)
# 真文号形态(如 苏工信〔2026〕123号)。仅匹配这种结构，避免把政策文件三公开表里的索引码
# (形如 696785044/2026-00017)误当文号；正文中对他文的文号引用风险较低，best-effort。
_DOC_NUMBER_RE = re.compile(r"[一-龥A-Za-z]{2,20}[〔\[（]\d{4}[〕\]）]\s*第?\s*\d+\s*号")
# 详情链接路径自带发布日期，如 /art/2026/4/17/art_80179_x.html
_URL_DATE_RE = re.compile(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/")


def _parse_publish_date(raw: Optional[str]) -> Optional[date]:
    """将 'YYYY-MM-DD' 安全解析为 date，失败返回 None。"""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _clean_dash(value: str) -> str:
    """将纯占位短横(如 '—  —')规整为空字符串。"""
    cleaned = (value or "").replace("\xa0", " ").strip()
    return "" if all(ch in _DASH_CHARS for ch in cleaned) else cleaned


def _date_from_url(url: str) -> Optional[date]:
    """从详情链接路径 /art/YYYY/M/D/ 派生发布日期(两套列表模板统一可靠的兜底)。"""
    m = _URL_DATE_RE.search(url or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _absolute_url(href: str) -> str:
    """详情链接为站内相对路径(/art/...)，补成绝对 URL(已是绝对则原样返回)。"""
    href = (href or "").strip()
    if not href or href.startswith(("http://", "https://")):
        return href
    return _BASE + href if href.startswith("/") else f"{_BASE}/{href}"


class GxtPolicyCrawler(PolicyCrawler):
    """江苏省工信厅门户政策爬虫(httpx + BeautifulSoup)。

    列表走大汉 dataproxy XML 接口按栏目翻页；详情页静态 HTML 补全正文。
    可选 `title_keyword`：仅保留标题含该词的条目(留作未来按"申报"等聚焦栏目子集)。
    """

    def __init__(
        self,
        page_size: int = _DEFAULT_PAGE_SIZE,
        request_delay: float = _REQUEST_DELAY,
        column_id: int = _COLUMN_ID,
        unit_id: str = _UNIT_ID,
        title_keyword: Optional[str] = None,
        source: str = _SOURCE,
    ) -> None:
        self._page_size = page_size
        self._request_delay = request_delay
        self._column_id = column_id
        self._unit_id = unit_id  # 每个栏目的 jpage 实例 id 不同(col6278=403981 / col80179=403740)
        self._title_keyword = title_keyword
        self._source = source

    @staticmethod
    def _parse_list_payload(
        xml_text: str, source: str = _SOURCE, title_keyword: Optional[str] = None,
    ) -> List[Policy]:
        """从 dataproxy XML 解析结构化政策(不含正文，由详情页补全)。

        每条记录的 CDATA 片段为 <li><a href title>标题</a><span>日期</span></li>；
        URL 相对路径补绝对；传 title_keyword 时仅保留标题命中的条目。
        """
        policies: List[Policy] = []
        for frag in _RECORD_RE.findall(xml_text or ""):
            soup = BeautifulSoup(frag, "html.parser")
            anchor = soup.find("a", href=True)
            if anchor is None:
                continue
            url = _absolute_url(anchor["href"])
            if not url:
                continue
            title = (anchor.get("title") or anchor.get_text(strip=True)).strip()
            if title_keyword and title_keyword not in title:
                continue
            # 日期元素两套模板不一(col6278=<span> / col80179=<b readlabel>)，文本取不到则从 URL 路径派生
            date_el = soup.find("span") or soup.find("b")
            publish_date = (
                _parse_publish_date(date_el.get_text(strip=True) if date_el else "")
                or _date_from_url(url)
            )
            policies.append(
                Policy(
                    source=source,
                    source_url=url,
                    title=title,
                    publish_date=publish_date,
                    region=_REGION,
                )
            )
        return policies

    def _total_pages(self, xml_text: str) -> int:
        """据 <totalrecord> 与当前页大小推总页数(接口的 totalpage 依赖请求 perpage，自算更稳)。"""
        match = _TOTAL_RE.search(xml_text or "")
        if not match:
            return 0
        return math.ceil(int(match.group(1)) / self._page_size)

    @staticmethod
    def _parse_detail(html: str) -> Tuple[str, str]:
        """从详情页 HTML 解析(正文, 文号)，兼容两套模板：

        - 文件通知(col6278)：正文在 div.article_zoom，多无文号表；
        - 政策文件(col80179)：正文在 div#Zoom，带三公开元数据表(但其'发文字号'常为索引码)。
        文号仅按真文号形态(〔YYYY〕N号)best-effort 提取，避免误收索引码；取不到留空。
        """
        soup = BeautifulSoup(html or "", "html.parser")

        body_el = (
            soup.select_one(".article_zoom")
            or soup.select_one("#Zoom")
            or soup.select_one(".view")
            or soup.select_one(".nscont")
            or soup.select_one("#con1")
        )
        body_text = body_el.get_text("\n", strip=True) if body_el else ""

        match = _DOC_NUMBER_RE.search(soup.get_text(" ", strip=True))
        doc_number = _clean_dash(match.group(0)) if match else ""
        return body_text, doc_number

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        """抓取最多 max_pages 页政策(含详情正文)，限速且对失败条目容错跳过。"""
        collected: List[Policy] = []
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA}, timeout=25, follow_redirects=True
        ) as client:
            for page in range(1, max_pages + 1):
                xml_text = await self._fetch_list(client, page)
                if xml_text is None:
                    break
                page_policies = self._parse_list_payload(
                    xml_text, self._source, self._title_keyword,
                )
                if not page_policies:
                    break
                for policy in page_policies:
                    await self._enrich_detail(client, policy)
                    collected.append(policy)
                    await asyncio.sleep(self._request_delay)
                if page >= self._total_pages(xml_text):
                    break
        logger.info(f"gxt 政策爬虫抓取完成，共 {len(collected)} 条")
        return collected

    async def _fetch_list(self, client: httpx.AsyncClient, page: int) -> Optional[str]:
        """抓取某页列表 XML(大汉 dataproxy)，失败返回 None。"""
        start = (page - 1) * self._page_size + 1
        end = page * self._page_size
        params = {
            "appid": "1",
            "webid": _WEB_ID,
            "path": "/",
            "columnid": self._column_id,
            "unitid": self._unit_id,
            "col": "1",
            "sourceContentType": "1",
            "permissiontype": "0",
            "webname": _WEBNAME,
            "startrecord": start,
            "endrecord": end,
            "perpage": self._page_size,
        }
        try:
            resp = await client.get(
                _LIST_API,
                params=params,
                headers={"Referer": f"{_BASE}/col/col{self._column_id}/index.html"},
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            logger.warning(f"gxt 政策列表第 {page} 页抓取失败: {type(e).__name__}: {e}")
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
