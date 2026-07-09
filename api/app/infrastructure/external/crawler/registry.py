"""公开政策爬虫来源注册表（通用多区域框架）。

每个地区/门户是一个 CrawlerSource(key/name/region + 爬虫工厂)。入库与前端按 source 选择来源；
新增一个地区 = 实现一个 PolicyCrawler + 在此登记一条 CrawlerSource，无需改动入库编排/端点。
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Set

from core.config import get_settings

from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.feed_item import FeedItemType
from app.infrastructure.external.crawler.cnmaker_contest_crawler import CnmakerContestCrawler
from app.infrastructure.external.crawler.cq_policy_crawler import CqPolicyCrawler
from app.infrastructure.external.crawler.gxt_policy_crawler import GxtPolicyCrawler
from app.infrastructure.external.crawler.shyp_policy_crawler import ShypPolicyCrawler
from app.infrastructure.external.crawler.wnd_policy_crawler import WndPolicyCrawler

# 赛事标题排除词：获奖公示/名单类通知从来不是"可报名的机会"，列表页即排除
# (风险收紧：真机首抓 gxt-contest 大半是历史获奖公示)。
_CONTEST_EXCLUDE_WORDS = ("获奖", "公示", "公布", "名单", "结果")


def _contest_filter_kwargs() -> dict:
    """赛事子源共用的保鲜过滤参数(时效窗口 CONTEST_MAX_AGE_DAYS 可调)。"""
    return {
        "max_age_days": get_settings().contest_max_age_days,
        "title_exclude": _CONTEST_EXCLUDE_WORDS,
    }


@dataclass(frozen=True)
class CrawlerSource:
    """一个政策来源：稳定的 key、展示名、适用地区、官网链接、构造爬虫的工厂。

    item_type 标记该来源产出的机会类型(缺省=政策)：赛事子源(如"大赛"关键词检索)
    标记为 competition，供 ④ Feed 物化时按 policy.source 打对应 type(预留扩展位)。
    """
    key: str
    name: str
    region: str
    factory: Callable[[], PolicyCrawler]
    home_url: str = ""  # 来源门户官网/栏目地址(供「数据来源」页溯源展示)
    item_type: FeedItemType = FeedItemType.POLICY  # 该来源产出的机会类型


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
    CrawlerSource(
        key="gxt-policy",
        name="江苏省工信厅门户·政策文件",
        region="江苏省",
        # 同门户「政策文件」栏目(col80179，jpage 实例 unitid=403740)：规范性文件，正文在 #Zoom。
        factory=lambda: GxtPolicyCrawler(
            column_id=80179, unit_id="403740", source="gxt-policy",
        ),
        home_url="https://gxt.jiangsu.gov.cn",
    ),
    # ---- 赛事子源(机会类型=competition)：创业类大赛的赛区通知本来就发省市门户，
    # 复用既有爬虫按标题关键词"大赛"检索/过滤，绕开公众号(比赛机会重启决策)。
    CrawlerSource(
        key="wnd-contest",
        name="无锡高新区(新吴区)门户·大赛通知",
        region="江苏省无锡市新吴区",
        factory=lambda: WndPolicyCrawler(
            title_keyword="大赛", source="wnd-contest", **_contest_filter_kwargs(),
        ),
        home_url="https://www.wnd.gov.cn",
        item_type=FeedItemType.COMPETITION,
    ),
    CrawlerSource(
        key="gxt-contest",
        name="江苏省工信厅门户·大赛通知",
        region="江苏省",
        # 「文件通知」栏目(缺省栏目)按标题含"大赛"过滤(创客中国/创新创业大赛等省赛通知)。
        factory=lambda: GxtPolicyCrawler(
            title_keyword="大赛", source="gxt-contest", **_contest_filter_kwargs(),
        ),
        home_url="https://gxt.jiangsu.gov.cn",
        item_type=FeedItemType.COMPETITION,
    ),
    # ---- 重庆市级赛事子源(PR3)：科技局办创新创业大赛/高新杯，经信委办创客中国重庆赛区。
    # 两站同属 TRS WCM 静态站(2026-07-07 逆向)，CqPolicyCrawler 按栏目参数化复用。
    CrawlerSource(
        key="cqkjj-contest",
        name="重庆市科技局门户·大赛通知",
        region="重庆市",
        factory=lambda: CqPolicyCrawler(
            base_url="https://kjj.cq.gov.cn",
            column_path="/zwxx_176/tzgg/",  # 通知公告栏目
            source="cqkjj-contest",
            title_keyword="大赛",
            **_contest_filter_kwargs(),
        ),
        home_url="https://kjj.cq.gov.cn",
        item_type=FeedItemType.COMPETITION,
    ),
    CrawlerSource(
        key="cqjjw-contest",
        name="重庆市经信委门户·大赛通知",
        region="重庆市",
        factory=lambda: CqPolicyCrawler(
            base_url="https://jjxxw.cq.gov.cn",
            column_path="/zwgk_213/gsgg/",  # 公示公告栏目(创客中国重庆赛区通知阵地)
            source="cqjjw-contest",
            title_keyword="大赛",
            **_contest_filter_kwargs(),
        ),
        home_url="https://jjxxw.cq.gov.cn",
        item_type=FeedItemType.COMPETITION,
    ),
    # ---- 全国赛事平台(创客中国官网)：一个来源覆盖各省市赛区 + 全国性行业赛(2026-07-08 逆向)。
    # 首页静态主推当季赛事，产出多地区(policy.region 各自标准化)，前端参赛地区选项由实际
    # 入库赛事地区去重驱动(见 PolicyService.list_contest_regions)，故 source.region 仅作
    # 「数据来源」页展示的代表值。
    CrawlerSource(
        key="cnmaker-contest",
        name="创客中国官网·全国中小企业创新创业大赛",
        region="全国",
        factory=lambda: CnmakerContestCrawler(**_contest_filter_kwargs()),
        home_url="https://www.cnmaker.org.cn",
        item_type=FeedItemType.COMPETITION,
    ),
]


def competition_source_keys() -> Set[str]:
    """返回全部赛事来源的 key(供 Feed 物化把这些来源的条目打 type=competition)。"""
    return {s.key for s in CRAWLER_SOURCES if s.item_type == FeedItemType.COMPETITION}


# 创客中国常设赛区：官网确有这些城市赛区，但首页当季未主推(动态全量接口被 SiteBuilder
# 令牌网关挡住、无法稳定抓取)，故 DB 暂无数据。作为"关注偏好"并入「参赛关注地区」选项，
# 便于用户预选——数据一旦入库(map_region 已输出同一 region 串)即在工作台出现并按此推送。
# region 串须与 CnmakerContestCrawler.map_region 的输出保持一致。
CURATED_CONTEST_REGIONS = ("上海市", "湖北省武汉市")


def list_sources() -> List[CrawlerSource]:
    """返回全部已登记来源(供前端来源选择器与 /policies/sources)。"""
    return list(CRAWLER_SOURCES)


def build_crawlers() -> Dict[str, PolicyCrawler]:
    """按 key 构造各来源的爬虫实例(爬虫构造轻量、无 IO)。"""
    return {s.key: s.factory() for s in CRAWLER_SOURCES}
