"""将平台管理员配置映射为已验证的赛事爬虫模板。"""

from app.application.errors.exceptions import BadRequestError
from app.domain.external.policy_crawler import PolicyCrawler
from app.domain.models.contest import ContestSource
from app.infrastructure.external.crawler.cnmaker_contest_crawler import CnmakerContestCrawler
from app.infrastructure.external.crawler.cq_policy_crawler import CqPolicyCrawler
from app.infrastructure.external.crawler.gxt_policy_crawler import GxtPolicyCrawler
from app.infrastructure.external.crawler.wnd_policy_crawler import WndPolicyCrawler
from core.config import get_settings

SUPPORTED_CONTEST_ADAPTERS = {"cnmaker", "wnd", "gxt", "cq"}
_EXCLUDE = ("获奖", "公示", "公布", "名单", "结果")


def build_contest_crawler(source: ContestSource) -> PolicyCrawler:
    """仅构造已验证 CMS 模板；拒绝任意 URL 的通用抓取。"""
    config = source.adapter_config or {}
    common = {"max_age_days": get_settings().contest_max_age_days, "title_exclude": _EXCLUDE}
    if source.adapter_type == "cnmaker":
        return CnmakerContestCrawler(source=source.key, **common)
    if source.adapter_type == "wnd":
        return WndPolicyCrawler(title_keyword=config.get("title_keyword", "大赛"), source=source.key, **common)
    if source.adapter_type == "gxt":
        return GxtPolicyCrawler(title_keyword=config.get("title_keyword", "大赛"), source=source.key, **common)
    if source.adapter_type == "cq":
        base_url, column_path = config.get("base_url", ""), config.get("column_path", "")
        if not base_url or not column_path:
            raise BadRequestError("重庆 TRS 模板需要 base_url 和 column_path")
        return CqPolicyCrawler(base_url=base_url, column_path=column_path, source=source.key,
                               title_keyword=config.get("title_keyword", "大赛"), **common)
    raise BadRequestError(f"不支持的赛事来源模板：{source.adapter_type}")
