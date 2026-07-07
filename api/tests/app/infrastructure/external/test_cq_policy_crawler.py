"""CqPolicyCrawler 纯解析单元测试：不触网，用真实页面结构的 fixture 驱动。

覆盖重庆市级门户两套 TRS WCM 列表模板(科技局 kjj=li+兄弟span / 经信委 jjxxw=a>p+内嵌span)、
静态分页 createPage 总页数、详情正文 trs_editor_view、URL 路径日期兜底与赛事保鲜过滤接线。
"""

import asyncio
from datetime import date, timedelta

from app.infrastructure.external.crawler.cq_policy_crawler import (
    CqPolicyCrawler,
    _date_from_url,
    _parse_publish_date,
)

# kjj.cq.gov.cn 通知公告(zwxx_176/tzgg)真实列表结构(节选)：li 内 a(title 属性) + 兄弟 span 日期
_LIST_HTML_KJJ = """
<ul class="list">
  <li class="clearfix"><a href="./202607/t20260702_15795188.html" target="_blank"
    title="重庆市科学技术局关于第二届“渝创星火”重庆科技成果转化大赛报名延期的通知">重庆市科学技术局关于第二届“渝创星火”重庆科技成果转化大赛报名延期的通知</a><span>2026-07-02</span></li>
  <li class="clearfix"><a href="./202607/t20260707_15805740.html" target="_blank"
    title="重庆市科学技术局关于2026年第六批入库科技型企业名单的公告">重庆市科学技术局关于2026年第六批入库科技型企业名单的公告</a><span>2026-07-07</span></li>
  <li><a href="/zwgk_176/fdzdgknr/czyjs/">无详情链接的栏目导航</a></li>
</ul>
<script>
//wcm分页，总记录：2
createPage(34, 0, "index", "html");
function createPage(_nPageCount, _nCurrIndex, _sPageName, _sPageExt) {}
</script>
"""

# jjxxw.cq.gov.cn 公示公告(zwgk_213/gsgg)真实列表结构(节选)：a 内嵌 p 标题 + span 日期
_LIST_HTML_JJXXW = """
<div class="list">
 <a href="./202607/t20260706_15802464.html">
            <p>关于重庆食品包装设计大赛入围作品的公示</p>
            <span>2026-07-06</span> </a>
 <a href="./202607/t20260703_15798287.html">
            <p>关于拟增补入选市经济信息委专家库人员名单的公示</p>
            <span>2026-07-03</span> </a>
</div>
<script>createPage(40, 0, "index", "html");</script>
"""

# 详情页真实结构(节选)：正文在 trs_editor_view(kjj 外层还有 zwxl-article)
_DETAIL_HTML = """
<div class="zwxl-content">
  <div class="zwxl-article pages_content">
    <div class="trs_editor_view TRS_UEDITOR trs_paper_default trs_web">
      <p>各有关单位：</p>
      <p>大赛报名延期至7月17日，请尽快组织企业（团队）报名。渝科局发〔2026〕88号</p>
    </div>
  </div>
</div>
"""

_KJJ_LIST_URL = "https://kjj.cq.gov.cn/zwxx_176/tzgg/index.html"
_JJXXW_LIST_URL = "https://jjxxw.cq.gov.cn/zwgk_213/gsgg/index.html"


def _kjj_crawler(**kwargs) -> CqPolicyCrawler:
    return CqPolicyCrawler(
        base_url="https://kjj.cq.gov.cn",
        column_path="/zwxx_176/tzgg/",
        source="cqkjj-contest",
        request_delay=0,
        **kwargs,
    )


def test_parse_list_kjj_template_maps_fields() -> None:
    policies = CqPolicyCrawler._parse_list_page(
        _LIST_HTML_KJJ, _KJJ_LIST_URL, source="cqkjj-contest", region="重庆市",
    )

    assert len(policies) == 2  # 栏目导航等非详情链接被跳过
    first = policies[0]
    assert first.source == "cqkjj-contest"
    assert first.source_url == "https://kjj.cq.gov.cn/zwxx_176/tzgg/202607/t20260702_15795188.html"
    assert "渝创星火" in first.title
    assert first.publish_date == date(2026, 7, 2)
    assert first.region == "重庆市"


def test_parse_list_jjxxw_template_title_from_p() -> None:
    policies = CqPolicyCrawler._parse_list_page(
        _LIST_HTML_JJXXW, _JJXXW_LIST_URL, source="cqjjw-contest", region="重庆市",
    )

    assert len(policies) == 2
    assert policies[0].title == "关于重庆食品包装设计大赛入围作品的公示"
    assert policies[0].publish_date == date(2026, 7, 6)
    assert policies[0].source_url == (
        "https://jjxxw.cq.gov.cn/zwgk_213/gsgg/202607/t20260706_15802464.html"
    )


def test_date_falls_back_to_url_path_when_span_missing() -> None:
    html = '<li><a href="./202605/t20260518_123.html" title="关于举办大赛的通知">关于举办大赛的通知</a></li>'
    policies = CqPolicyCrawler._parse_list_page(
        html, _KJJ_LIST_URL, source="cqkjj-contest", region="重庆市",
    )

    assert policies[0].publish_date == date(2026, 5, 18)


def test_total_pages_from_createpage_invocation() -> None:
    assert CqPolicyCrawler._total_pages(_LIST_HTML_KJJ) == 34
    assert CqPolicyCrawler._total_pages(_LIST_HTML_JJXXW) == 40
    assert CqPolicyCrawler._total_pages("<html>no pager</html>") == 0


def test_page_url_static_pagination() -> None:
    crawler = _kjj_crawler()
    assert crawler._page_url(1) == "https://kjj.cq.gov.cn/zwxx_176/tzgg/index.html"
    assert crawler._page_url(2) == "https://kjj.cq.gov.cn/zwxx_176/tzgg/index_1.html"
    assert crawler._page_url(5) == "https://kjj.cq.gov.cn/zwxx_176/tzgg/index_4.html"


def test_parse_detail_body_from_trs_editor_view() -> None:
    body, doc_number = CqPolicyCrawler._parse_detail(_DETAIL_HTML)

    assert "延期至7月17日" in body
    assert doc_number == "渝科局发〔2026〕88号"


def test_parse_detail_handles_missing_body() -> None:
    body, doc_number = CqPolicyCrawler._parse_detail("<html><body>404</body></html>")

    assert body == ""
    assert doc_number == ""


def test_crawl_filters_by_keyword_and_keeps_paginating() -> None:
    """关键词过滤后某页为空 ≠ 到底(与 gxt 同教训)：翻页须继续。"""
    pages = {
        1: _LIST_HTML_JJXXW.replace("大赛", "征集"),  # 第1页无"大赛"
        2: _LIST_HTML_JJXXW,  # 第2页命中1条(入围公示含"大赛")
    }
    crawler = _kjj_crawler(title_keyword="大赛")
    fetched: list = []

    async def fake_fetch_page(client, page):
        fetched.append(page)
        return pages.get(page)

    async def fake_enrich(client, policy):
        policy.body_text = "正文"

    crawler._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    crawler._enrich_detail = fake_enrich  # type: ignore[method-assign]

    policies = asyncio.run(crawler.crawl(max_pages=2))

    assert fetched == [1, 2]
    assert len(policies) == 1
    assert "大赛" in policies[0].title


def test_crawl_contest_mode_skips_stale_and_stops_early() -> None:
    """赛事保鲜接线：时效窗口外/排除词条目详情前跳过，整页过旧提前停止翻页。"""
    today = date.today()
    fresh = (today - timedelta(days=10)).isoformat()
    stale = (today - timedelta(days=400)).isoformat()

    def _li(href: str, title: str, d: str) -> str:
        return f'<li><a href="{href}" title="{title}">{title}</a><span>{d}</span></li>'

    pages = {
        1: (
            _li("./202606/t20260627_1.html", "关于举办高新杯众创大赛的通知", fresh)
            + _li("./202606/t20260626_2.html", "关于公布大赛获奖名单的通知", fresh)
            + '<script>createPage(3, 0, "index", "html");</script>'
        ),
        2: (
            _li("./202305/t20230501_3.html", "关于举办2023大赛的通知", stale)
            + '<script>createPage(3, 0, "index", "html");</script>'
        ),
        3: _li("./202606/t20260601_4.html", "不应被抓到的大赛", fresh),
    }
    crawler = _kjj_crawler(
        title_keyword="大赛", max_age_days=180,
        title_exclude=("获奖", "公示", "公布", "名单", "结果"),
    )
    fetched: list = []
    enriched: list = []

    async def fake_fetch_page(client, page):
        fetched.append(page)
        return pages.get(page)

    async def fake_enrich(client, policy):
        enriched.append(policy.source_url)
        policy.body_text = "正文"

    crawler._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    crawler._enrich_detail = fake_enrich  # type: ignore[method-assign]

    policies = asyncio.run(crawler.crawl(max_pages=3))

    assert len(policies) == 1
    assert "高新杯" in policies[0].title
    assert len(enriched) == 1  # 排除词/过旧条目未抓详情
    assert fetched == [1, 2]  # 第2页整页过旧 → 不再翻第3页


def test_registry_exposes_cq_contest_sources() -> None:
    from app.domain.models.feed_item import FeedItemType
    from app.infrastructure.external.crawler.registry import (
        build_crawlers,
        competition_source_keys,
        list_sources,
    )

    by_key = {s.key: s for s in list_sources()}
    for key in ("cqkjj-contest", "cqjjw-contest"):
        assert key in by_key
        assert by_key[key].region == "重庆市"
        assert by_key[key].item_type == FeedItemType.COMPETITION
        assert key in competition_source_keys()
    # 工厂可构造出可用爬虫
    crawlers = build_crawlers()
    assert hasattr(crawlers["cqkjj-contest"], "crawl")


def test_parse_publish_date_and_date_from_url_helpers() -> None:
    assert _parse_publish_date("2026-07-02") == date(2026, 7, 2)
    assert _parse_publish_date("垃圾") is None
    assert _date_from_url("https://x/202607/t20260702_15795188.html") == date(2026, 7, 2)
    assert _date_from_url("https://x/nodate.html") is None
