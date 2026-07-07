"""赛事列表级过滤纯函数单测：时效窗口 / 标题排除词 / 整页过旧早停判定。"""

from datetime import date

from app.domain.models.policy import Policy
from app.infrastructure.external.crawler.list_filter import (
    filter_list_items,
    freshness_cutoff,
    page_all_stale,
)

_TODAY = date(2026, 7, 7)


def _p(title: str, publish: date | None) -> Policy:
    return Policy(source_url=f"url-{title}", title=title, publish_date=publish)


def test_freshness_cutoff_from_max_age_days() -> None:
    assert freshness_cutoff(180, today=_TODAY) == date(2026, 1, 8)
    # None/0/负值 = 不限
    assert freshness_cutoff(None, today=_TODAY) is None
    assert freshness_cutoff(0, today=_TODAY) is None
    assert freshness_cutoff(-1, today=_TODAY) is None


def test_filter_drops_items_before_cutoff_keeps_fresh_and_undated() -> None:
    cutoff = date(2026, 1, 8)
    fresh = _p("新大赛", date(2026, 6, 1))
    stale = _p("旧大赛", date(2023, 6, 1))
    undated = _p("缺日期大赛", None)  # 缺日期保留，交后续环节兜底(宁缺勿滥)

    kept = filter_list_items([fresh, stale, undated], cutoff)

    assert kept == [fresh, undated]


def test_filter_drops_result_announcement_titles() -> None:
    """获奖公示/名单类标题不是"可报名的机会"，不论多新都排除。"""
    exclude = ("获奖", "公示", "公布", "名单", "结果")
    actionable = _p("关于举办2026创新创业大赛的通知", date(2026, 6, 1))
    result_notice = _p("关于公布2026大赛获奖名单的通知", date(2026, 6, 1))

    kept = filter_list_items([actionable, result_notice], None, exclude)

    assert kept == [actionable]


def test_filter_without_cutoff_or_exclude_is_noop() -> None:
    items = [_p("大赛A", date(2020, 1, 1)), _p("获奖公示", None)]
    assert filter_list_items(items, None) == items


def test_page_all_stale_only_when_every_item_dated_and_old() -> None:
    cutoff = date(2026, 1, 8)
    old_a = _p("旧A", date(2023, 1, 1))
    old_b = _p("旧B", date(2024, 1, 1))
    fresh = _p("新", date(2026, 6, 1))
    undated = _p("缺日期", None)

    assert page_all_stale([old_a, old_b], cutoff) is True
    # 保守判定：有新条目 / 有缺日期条目 / 空页 / 无窗口 → 都不能早停
    assert page_all_stale([old_a, fresh], cutoff) is False
    assert page_all_stale([old_a, undated], cutoff) is False
    assert page_all_stale([], cutoff) is False
    assert page_all_stale([old_a], None) is False
