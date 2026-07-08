"""赛事来源的列表级过滤纯函数(主线②赛事子源保鲜)。

比赛通知有明确生命周期：超过时效窗口的基本已报名截止，获奖公示/名单类标题
从来不是"可报名的机会"。在列表解析后、详情抓取前过滤，省下详情页 HTTP、
LLM 截止抽取与向量化三笔开销；列表按日期倒序时整页过旧还可提前停止翻页。
政策来源不接线此过滤(政策长期有效)。
"""

from datetime import date, timedelta
from typing import List, Optional, Sequence

from app.domain.models.policy import Policy


def freshness_cutoff(max_age_days: Optional[int], today: Optional[date] = None) -> Optional[date]:
    """时效窗口起点日期；max_age_days 为 None/非正 = 不限(返回 None)。"""
    if not max_age_days or max_age_days <= 0:
        return None
    return (today or date.today()) - timedelta(days=max_age_days)


def filter_list_items(
    policies: List[Policy],
    cutoff: Optional[date],
    title_exclude: Sequence[str] = (),
) -> List[Policy]:
    """按时效窗口与标题排除词过滤列表条目，返回新列表。

    缺发布日期的条目保留(宁缺勿滥，交入库侧截止判定兜底)；
    cutoff=None 跳过时效判定，title_exclude 为空跳过排除词判定。
    """
    kept: List[Policy] = []
    for policy in policies:
        if cutoff and policy.publish_date and policy.publish_date < cutoff:
            continue
        if any(word in policy.title for word in title_exclude):
            continue
        kept.append(policy)
    return kept


def page_all_stale(policies: List[Policy], cutoff: Optional[date]) -> bool:
    """整页原始记录都早于时效窗口(列表按日期倒序时可据此提前停止翻页)。

    保守判定：空页、无窗口、或存在缺日期/窗口内条目时都返回 False，宁多翻不漏抓。
    """
    if not policies or cutoff is None:
        return False
    return all(p.publish_date is not None and p.publish_date < cutoff for p in policies)
