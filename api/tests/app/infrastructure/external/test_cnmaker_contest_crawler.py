"""CnmakerContestCrawler 纯解析单元测试：不触网，用真实首页结构的 fixture 驱动。

覆盖创客中国官网首页赛事列表(a.game_boll：状态/标题/分类-年月)、按 source_url 去重、
排除"已结束"、分类→标准 region 映射、详情正文 competition-intronr、赛事保鲜过滤接线。
"""

import asyncio
from datetime import date, timedelta

from app.infrastructure.external.crawler.cnmaker_contest_crawler import (
    CnmakerContestCrawler,
    _parse_year_month,
    map_region,
)

# 官网首页(www.cnmaker.org.cn)真实赛事条目结构(节选)：地区赛 + 行业赛 + 已结束 + 重复条目
_LIST_HTML = """
<div class="game_box">
  <a class="game_boll" href="ds/detail/aaa111.html">
    <label class="tips">进行中</label>
    <p class="sc_img"><img src="/upload/x.jpg"/></p>
    <h3>深圳市中小企业服务局关于举办第十一届“创客中国”深圳市中小企业创新创业大赛的通知</h3>
    <p><span>分类：深圳</span><span>2026-04</span></p>
  </a>
  <a class="game_boll" href="ds/detail/bbb222.html">
    <label class="tips">进行中</label>
    <h3>第十一届“创客中国”医药健康 中小企业创新创业大赛的通知</h3>
    <p><span>分类：生物医药</span><span>2026-06</span></p>
  </a>
  <a class="game_boll" href="ds/detail/ccc333.html">
    <label class="tips">预热中</label>
    <h3>第十一届“创客中国”云南省中小企业创新创业大赛</h3>
    <p><span>分类：云南</span><span>2026-08</span></p>
  </a>
  <a class="game_boll" href="ds/detail/ddd444.html">
    <label class="tips">已结束</label>
    <h3>第十一届“创客中国”增材制造中小企业创新创业大赛</h3>
    <p><span>分类：增材制造</span><span>2026-04</span></p>
  </a>
  <a class="game_boll" href="ds/detail/aaa111.html">
    <label class="tips">进行中</label>
    <h3>深圳市中小企业服务局关于举办第十一届“创客中国”深圳市中小企业创新创业大赛的通知</h3>
    <p><span>分类：深圳</span><span>2026-04</span></p>
  </a>
</div>
"""

_DETAIL_HTML = """
<div class="competition-info">
  <div class="competition-intronr">
    <p>各有关企业和创客：</p>
    <p>报名时间：本通知发布之日起至2026年7月10日。</p>
  </div>
</div>
"""


def test_parse_list_extracts_fields_and_maps_region() -> None:
    policies = CnmakerContestCrawler._parse_list(
        _LIST_HTML, source="cnmaker-contest", exclude_status=("已结束",),
    )

    by_url = {p.source_url: p for p in policies}
    shenzhen = by_url["https://www.cnmaker.org.cn/ds/detail/aaa111.html"]
    assert shenzhen.source == "cnmaker-contest"
    assert "深圳市" in shenzhen.title
    assert shenzhen.region == "广东省深圳市"  # 简称"深圳"映射到省市层级串
    assert shenzhen.publish_date == date(2026, 4, 1)  # "2026-04" → 该月一号
    # 行业赛归"全国"，省全称保留
    assert by_url["https://www.cnmaker.org.cn/ds/detail/bbb222.html"].region == "全国"
    assert by_url["https://www.cnmaker.org.cn/ds/detail/ccc333.html"].region == "云南省"


def test_parse_list_dedupes_and_skips_ended() -> None:
    policies = CnmakerContestCrawler._parse_list(
        _LIST_HTML, source="cnmaker-contest", exclude_status=("已结束",),
    )

    urls = [p.source_url for p in policies]
    assert len(urls) == len(set(urls))  # 重复的 aaa111 只保留一次
    assert len(policies) == 3  # 深圳(去重后1) + 生物医药 + 云南；已结束的增材制造被排除
    assert all("增材制造" not in p.title for p in policies)


def test_map_region_variants() -> None:
    assert map_region("深圳") == "广东省深圳市"  # 地级市挂靠省
    assert map_region("北京") == "北京市"  # 直辖市
    assert map_region("新疆") == "新疆维吾尔自治区"  # 自治区简称
    assert map_region("云南省") == "云南省"  # 已是全称则原样
    assert map_region("生物医药") == "全国"  # 行业赛
    assert map_region("") == "全国"  # 空兜底
    assert map_region("武汉") == "湖北省武汉市"
    assert map_region("上海") == "上海市"


def test_parse_year_month() -> None:
    assert _parse_year_month("2026-04") == date(2026, 4, 1)
    assert _parse_year_month("2026.11") == date(2026, 11, 1)
    assert _parse_year_month("敬请期待") is None
    assert _parse_year_month("") is None


def test_parse_detail_body() -> None:
    body = CnmakerContestCrawler._parse_detail(_DETAIL_HTML)
    assert "报名时间" in body
    assert "2026年7月10日" in body


def test_parse_detail_handles_missing_body() -> None:
    assert CnmakerContestCrawler._parse_detail("<html><body>x</body></html>") == ""


def test_crawl_applies_freshness_and_fetches_detail() -> None:
    """保鲜接线：时效窗口外条目在详情抓取前跳过；列表去重排除后逐条补正文。"""
    old_ym = (date.today() - timedelta(days=400)).strftime("%Y-%m")
    html = _LIST_HTML + (
        '<a class="game_boll" href="ds/detail/old999.html"><label class="tips">进行中</label>'
        f'<h3>第十一届“创客中国”过旧省中小企业创新创业大赛</h3>'
        f'<p><span>分类：过旧</span><span>{old_ym}</span></p></a>'
    )
    crawler = CnmakerContestCrawler(max_age_days=180, request_delay=0)
    enriched: list = []

    async def fake_fetch(client, url):
        return html

    async def fake_enrich(client, policy):
        enriched.append(policy.source_url)
        policy.body_text = "正文"

    crawler._fetch = fake_fetch  # type: ignore[method-assign]
    crawler._enrich_detail = fake_enrich  # type: ignore[method-assign]

    policies = asyncio.run(crawler.crawl())

    titles = [p.title for p in policies]
    assert all("过旧" not in t for t in titles)  # 400 天前的条目被保鲜过滤
    assert len(policies) == 3
    assert len(enriched) == 3  # 仅保鲜后的条目抓详情


def test_registry_exposes_cnmaker_source() -> None:
    from app.domain.models.feed_item import FeedItemType
    from app.infrastructure.external.crawler.registry import (
        build_crawlers,
        competition_source_keys,
        list_sources,
    )

    by_key = {s.key: s for s in list_sources()}
    assert "cnmaker-contest" in by_key
    assert by_key["cnmaker-contest"].item_type == FeedItemType.COMPETITION
    assert "cnmaker-contest" in competition_source_keys()
    assert hasattr(build_crawlers()["cnmaker-contest"], "crawl")
