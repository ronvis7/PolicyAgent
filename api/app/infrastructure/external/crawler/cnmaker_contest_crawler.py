"""创客中国官网(cnmaker.org.cn)全国赛事爬虫。

数据源逆向(2026-07-08)：官网首页(www.cnmaker.org.cn)静态渲染了当季主推赛事列表，
每条为 `a.game_boll`——`label.tips` 状态(进行中/预热中/已结束)、`h3` 标题、
`p > span` 分类(地区/行业)与年月；详情链接 `ds/detail/{hash}.html` 服务端直出静态
HTML，正文在 `div.competition-intronr`(含主办/承办/报名时间)。完整赛事列表与地区
筛选走 SiteBuilder 多层封装的动态接口(getcompetitionlieb.xml)，逆向成本高且脆弱，
故只取首页静态主推(当季、可报名为主)，覆盖全国省市赛区 + 全国性行业赛。

与 wnd/shyp/gxt/cq 同属通用多区域框架：纯解析函数(_parse_list/_parse_detail/map_region)
与网络 I/O 分离便于单测；普通浏览器 UA + 限速、只取 HTML 正文不下载附件。一个来源
产出多地区赛事(policy.region 各自标准化)，前端参赛地区选项由实际入库赛事地区去重驱动。
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
from app.infrastructure.external.crawler.list_filter import filter_list_items, freshness_cutoff

logger = logging.getLogger(__name__)

_BASE = "https://www.cnmaker.org.cn"
_SOURCE = "cnmaker-contest"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_REQUEST_DELAY = 0.8  # 详情页之间的限速(秒)，对源站友好

# 列表分类可能是"YYYY-MM"月份，无日则视作当月一号(用于保鲜时效判定)
_YM_RE = re.compile(r"(\d{4})[-.](\d{1,2})")
# 全国性行业赛/未识别地区的兜底 region：任何地区企业均可报名
_NATIONWIDE = "全国"

# cnmaker「分类」简称 → 标准"省市"层级串(与 registry 来源 region 及层级前缀匹配对齐)。
# 命中即为地区赛区；未命中(行业赛如"生物医药""低空经济")归为全国。
_REGION_MAP = {
    # 直辖市
    "北京": "北京市", "上海": "上海市", "天津": "天津市", "重庆": "重庆市",
    # 省
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "台湾": "台湾省",
    # 自治区
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
    # 计划单列市/常见地级市赛区(挂靠所在省，便于"选省含市"层级匹配)
    "深圳": "广东省深圳市", "广州": "广东省广州市", "武汉": "湖北省武汉市",
    "苏州": "江苏省苏州市", "无锡": "江苏省无锡市", "南京": "江苏省南京市",
    "杭州": "浙江省杭州市", "宁波": "浙江省宁波市", "青岛": "山东省青岛市",
    "厦门": "福建省厦门市", "大连": "辽宁省大连市", "成都": "四川省成都市",
    "西安": "陕西省西安市", "长沙": "湖南省长沙市",
}


def map_region(category: str) -> str:
    """把 cnmaker「分类」标签映射为标准"省市"层级 region；行业赛/未识别归"全国"。

    先精确命中简称表；再兼容分类已是省/直辖市/自治区全称的情形；否则"全国"。
    """
    cat = (category or "").strip()
    if not cat:
        return _NATIONWIDE
    if cat in _REGION_MAP:
        return _REGION_MAP[cat]
    # 分类本身就是标准全称(如"云南省""内蒙古自治区")时原样保留
    if cat.endswith(("省", "市", "自治区")):
        return cat
    return _NATIONWIDE


def _parse_year_month(raw: Optional[str]) -> Optional[date]:
    """将"YYYY-MM"/"YYYY.MM"解析为该月一号 date，失败返回 None(缺日期条目保留)。"""
    m = _YM_RE.search(raw or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return None


class CnmakerContestCrawler(PolicyCrawler):
    """创客中国官网赛事爬虫(httpx + BeautifulSoup，首页静态列表 + 详情正文)。

    `exclude_status` 为要跳过的赛事状态(缺省跳过"已结束"，只留在报名/预热的机会)；
    `max_age_days`/`title_exclude` 为赛事保鲜过滤(见 list_filter，与其余赛事子源一致)。
    """

    def __init__(
        self,
        source: str = _SOURCE,
        request_delay: float = _REQUEST_DELAY,
        exclude_status: Sequence[str] = ("已结束",),
        max_age_days: Optional[int] = None,
        title_exclude: Sequence[str] = (),
    ) -> None:
        self._source = source
        self._request_delay = request_delay
        self._exclude_status = tuple(exclude_status)
        self._max_age_days = max_age_days
        self._title_exclude = title_exclude

    @classmethod
    def _parse_list(cls, html: str, source: str, exclude_status: Sequence[str]) -> List[Policy]:
        """从首页 HTML 解析赛事列表(不含正文)，按 source_url 去重、跳过指定状态。

        首页多个 tab 会重复渲染同一赛事，按详情 URL 去重取首次出现。
        """
        soup = BeautifulSoup(html or "", "html.parser")
        policies: List[Policy] = []
        seen: set = set()
        for a in soup.select("a.game_boll"):
            href = a.get("href")
            if not href:
                continue
            url = urljoin(_BASE + "/", href)
            if url in seen:
                continue
            tips = a.find("label", class_="tips")
            status = tips.get_text(strip=True) if tips else ""
            if status in exclude_status:
                continue
            h3 = a.find("h3")
            title = h3.get_text(strip=True) if h3 else ""
            if not title:
                continue
            category, ym = cls._extract_category_date(a)
            seen.add(url)
            policies.append(Policy(
                source=source,
                source_url=url,
                title=title,
                publish_date=_parse_year_month(ym),
                region=map_region(category),
            ))
        return policies

    @staticmethod
    def _extract_category_date(anchor) -> Tuple[str, str]:
        """从条目内 `<p><span>分类：X</span><span>YYYY-MM</span></p>` 取(分类, 年月)。"""
        category, ym = "", ""
        for span in anchor.find_all("span"):
            text = span.get_text(strip=True)
            if text.startswith("分类"):
                category = text.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif _YM_RE.search(text):
                ym = text
        return category, ym

    @staticmethod
    def _parse_detail(html: str) -> str:
        """从详情页 HTML 取正文(div.competition-intronr)，取不到返回空串。"""
        soup = BeautifulSoup(html or "", "html.parser")
        body_el = soup.select_one(".competition-intronr") or soup.select_one(".competition-intro")
        return body_el.get_text("\n", strip=True) if body_el else ""

    async def crawl(self, max_pages: int = 1) -> List[Policy]:
        """抓取首页当季赛事(含详情正文)。首页即全部主推，max_pages 仅为接口一致性保留。"""
        cutoff = freshness_cutoff(self._max_age_days)
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA}, timeout=25, follow_redirects=True
        ) as client:
            html = await self._fetch(client, _BASE + "/")
            if html is None:
                return []
            policies = self._parse_list(html, self._source, self._exclude_status)
            policies = filter_list_items(policies, cutoff, self._title_exclude)
            for policy in policies:
                await self._enrich_detail(client, policy)
                await asyncio.sleep(self._request_delay)
        logger.info(f"cnmaker 赛事爬虫({self._source})抓取完成，共 {len(policies)} 条")
        return policies

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """抓取页面 HTML，失败返回 None。"""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            logger.warning(f"cnmaker 页面抓取失败[{url}]: {type(e).__name__}: {e}")
            return None

    async def _enrich_detail(self, client: httpx.AsyncClient, policy: Policy) -> None:
        """抓取详情页补全正文；失败保留列表已得字段，不中断整批。"""
        try:
            resp = await client.get(policy.source_url)
            resp.raise_for_status()
            policy.body_text = self._parse_detail(resp.text)
            policy.crawled_at = datetime.now()
        except httpx.HTTPError as e:
            logger.warning(f"赛事详情页抓取失败[{policy.source_url}]: {type(e).__name__}: {e}")
