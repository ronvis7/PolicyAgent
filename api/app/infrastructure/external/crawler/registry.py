"""公开政策爬虫来源注册表（通用多区域框架）。

每个地区/门户是一个 CrawlerSource(key/name/region + 爬虫工厂)。入库与前端按 source 选择来源；
新增一个地区 = 实现一个 PolicyCrawler + 在此登记一条 CrawlerSource，无需改动入库编排/端点。
"""

from dataclasses import dataclass
from typing import Callable, Dict, List

from app.domain.external.policy_crawler import PolicyCrawler
from app.infrastructure.external.crawler.gxt_policy_crawler import GxtPolicyCrawler
from app.infrastructure.external.crawler.shyp_policy_crawler import ShypPolicyCrawler
from app.infrastructure.external.crawler.wnd_policy_crawler import WndPolicyCrawler


@dataclass(frozen=True)
class CrawlerSource:
    """一个政策来源：稳定的 key、展示名、适用地区、官网链接、构造爬虫的工厂。"""
    key: str
    name: str
    region: str
    factory: Callable[[], PolicyCrawler]
    home_url: str = ""  # 来源门户官网/栏目地址(供「数据来源」页溯源展示)


# 已登记的政策来源。新增地区/栏目在此追加一条即可。
# 同一门户可登记多个来源：政策文件(规范性文件)与项目申报通知(含申报截止日期，供主线⑤)。
CRAWLER_SOURCES: List[CrawlerSource] = [
    CrawlerSource(
        key="wnd",
        name="无锡高新区(新吴区)门户·政策文件",
        region="江苏省无锡市新吴区",
        factory=WndPolicyCrawler,
        home_url="https://www.wnd.gov.cn",
    ),
    CrawlerSource(
        key="wnd-apply",
        name="无锡高新区(新吴区)门户·项目申报通知",
        region="江苏省无锡市新吴区",
        factory=lambda: WndPolicyCrawler(title_keyword="申报", source="wnd-apply"),
        home_url="https://www.wnd.gov.cn",
    ),
    CrawlerSource(
        key="shyp",
        name="上海杨浦区门户·政府文件",
        region="上海市杨浦区",
        factory=ShypPolicyCrawler,
        home_url="https://www.shyp.gov.cn",
    ),
    CrawlerSource(
        key="gxt",
        name="江苏省工信厅门户·文件通知(含项目申报)",
        region="江苏省",
        factory=GxtPolicyCrawler,
        home_url="https://gxt.jiangsu.gov.cn",
    ),
]


def list_sources() -> List[CrawlerSource]:
    """返回全部已登记来源(供前端来源选择器与 /policies/sources)。"""
    return list(CRAWLER_SOURCES)


def build_crawlers() -> Dict[str, PolicyCrawler]:
    """按 key 构造各来源的爬虫实例(爬虫构造轻量、无 IO)。"""
    return {s.key: s.factory() for s in CRAWLER_SOURCES}
