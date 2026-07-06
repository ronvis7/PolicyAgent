"""爬虫来源注册表单测：赛事子源登记与机会类型分类(比赛机会重启)。

赛事路线=政府门户关键词子源("大赛")绕开公众号：各大赛赛区通知本来就发省市门户，
复用既有爬虫的 title_keyword 模式。registry 按 item_type 标记来源产出的机会类型，
供 Feed 物化时把赛事来源的条目打成 type=competition(④ 预留扩展位)。
"""

from app.domain.models.feed_item import FeedItemType
from app.infrastructure.external.crawler.registry import (
    build_crawlers,
    competition_source_keys,
    list_sources,
)


def test_contest_sources_registered_with_region_and_home_url() -> None:
    """wnd-contest/gxt-contest 已登记，带地区与官网(供「数据来源」页溯源)。"""
    by_key = {s.key: s for s in list_sources()}

    assert "wnd-contest" in by_key
    assert "gxt-contest" in by_key
    assert by_key["wnd-contest"].region == "江苏省无锡市新吴区"
    assert by_key["gxt-contest"].region == "江苏省"
    assert by_key["wnd-contest"].home_url
    assert by_key["gxt-contest"].home_url


def test_competition_source_keys_returns_only_contest_sources() -> None:
    """机会类型分类：仅赛事子源被归为 competition，政策来源不受影响。"""
    keys = competition_source_keys()

    assert keys == {"wnd-contest", "gxt-contest"}


def test_policy_sources_default_item_type_is_policy() -> None:
    """既有来源缺省仍是政策类型(向后兼容，Feed 打标不受影响)。"""
    by_key = {s.key: s for s in list_sources()}

    for key in ("wnd", "wnd-apply", "shyp", "gxt", "gxt-policy"):
        assert by_key[key].item_type == FeedItemType.POLICY


def test_contest_crawler_factories_use_dasai_keyword_and_source_key() -> None:
    """赛事子源工厂构造的爬虫按"大赛"关键词检索、source 标识与 key 一致(入库溯源)。"""
    crawlers = build_crawlers()

    wnd_contest = crawlers["wnd-contest"]
    gxt_contest = crawlers["gxt-contest"]
    # 构造参数为爬虫私有态，registry 工厂是唯一出口，这里直接断言以钉死配置
    assert wnd_contest._title_keyword == "大赛"  # noqa: SLF001
    assert wnd_contest._source == "wnd-contest"  # noqa: SLF001
    assert gxt_contest._title_keyword == "大赛"  # noqa: SLF001
    assert gxt_contest._source == "gxt-contest"  # noqa: SLF001


def test_build_crawlers_covers_every_registered_source() -> None:
    """每条登记来源都能构造出爬虫(工厂无 IO、构造即可用)。"""
    crawlers = build_crawlers()

    assert set(crawlers) == {s.key for s in list_sources()}
