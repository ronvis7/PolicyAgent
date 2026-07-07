"""WndPolicyCrawler 纯解析单元测试：不触网，用真实接口/页面结构的 fixture 驱动。"""

from datetime import date

from app.infrastructure.external.crawler.wnd_policy_crawler import (
    WndPolicyCrawler,
    _clean_dash,
    _parse_publish_date,
)

# 列表接口 /info_open/search 的真实返回结构(节选)
_LIST_PAYLOAD = {
    "status": 0,
    "data": {
        "totalElements": 82,
        "totalPages": 28,
        "page": 1,
        "data": [
            {
                "title": "关于印发无锡市优化营商环境行动方案（2026版）的通知",
                "writeTime": "2026-06-03",
                "openTime": "2026-06-03",
                "indexId": "014032126/2026-00903",
                "url": "http://www.wnd.gov.cn/doc/2026/06/03/4790460.shtml",
                "effectStatus": "有效",
                "organization": "空港经开区",
            },
            {  # 缺 url 的脏数据应被跳过
                "title": "无效条目",
                "url": "",
            },
        ],
    },
}

# 详情页真实结构(节选)：正文在 div#Zoom，文号在 table.xxgk_table_wza 的"文件编号"
_DETAIL_HTML = """
<div class="content doc_content_wza">
  <h3 class="font36">关于印发无锡市优化营商环境行动方案的通知</h3>
  <p class="date">时间：2026-06-03</p>
  <table class="xxgk_table_wza">
    <tr><th>信息索引号</th><td>014032126/2026-00903</td><th>公开日期</th><td>2026-06-03</td></tr>
    <tr><th>文件编号</th><td>锡新政发〔2026〕1号</td><th>效力状况</th><td>有效</td></tr>
  </table>
  <div id="Zoom"><p>第一条 为优化营商环境，制定本方案。</p><p>第二条 本方案自发布之日起施行。</p></div>
</div>
"""


def test_parse_list_payload_maps_fields_and_skips_blank_url() -> None:
    policies = WndPolicyCrawler._parse_list_payload(_LIST_PAYLOAD)

    assert len(policies) == 1  # 缺 url 的脏数据被跳过
    p = policies[0]
    assert p.source == "wnd"
    assert p.source_url == "http://www.wnd.gov.cn/doc/2026/06/03/4790460.shtml"
    assert p.index_number == "014032126/2026-00903"
    assert p.title.startswith("关于印发无锡市优化营商环境")
    assert p.issuer == "空港经开区"
    assert p.status == "有效"
    assert p.publish_date == date(2026, 6, 3)
    assert p.region == "江苏省无锡市新吴区"
    assert p.body_text == ""  # 正文由详情页补全


def test_parse_list_payload_uses_given_source() -> None:
    # 申报模式以不同 source 入库(便于区分政策文件 / 申报通知)
    policies = WndPolicyCrawler._parse_list_payload(_LIST_PAYLOAD, source="wnd-apply")
    assert policies[0].source == "wnd-apply"
    assert policies[0].region == "江苏省无锡市新吴区"  # 同一门户地区不变


def test_apply_mode_fetch_uses_title_keyword_not_channels() -> None:
    # 申报模式按 title 关键词全站检索，不带 channelIds；记录实际发出的表单
    crawler = WndPolicyCrawler(title_keyword="申报", source="wnd-apply")
    sent = {}

    class _Resp:
        def raise_for_status(self): ...
        def json(self): return _LIST_PAYLOAD

    class _Client:
        async def post(self, url, data=None, headers=None):
            sent.update(data or {})
            return _Resp()

    import asyncio
    asyncio.run(crawler._fetch_list(_Client(), 1))
    assert sent.get("title") == "申报"
    assert "channelIds" not in sent


def test_default_mode_fetch_uses_channels_not_title() -> None:
    crawler = WndPolicyCrawler()
    sent = {}

    class _Resp:
        def raise_for_status(self): ...
        def json(self): return _LIST_PAYLOAD

    class _Client:
        async def post(self, url, data=None, headers=None):
            sent.update(data or {})
            return _Resp()

    import asyncio
    asyncio.run(crawler._fetch_list(_Client(), 1))
    assert "channelIds" in sent
    assert "title" not in sent


def test_total_pages_reads_pagination() -> None:
    assert WndPolicyCrawler._total_pages(_LIST_PAYLOAD) == 28
    assert WndPolicyCrawler._total_pages({}) == 0


def test_parse_detail_extracts_body_and_doc_number() -> None:
    body, doc_number = WndPolicyCrawler._parse_detail(_DETAIL_HTML)

    assert "第一条" in body and "第二条" in body
    assert doc_number == "锡新政发〔2026〕1号"


def test_parse_detail_handles_missing_body_and_dash_doc_number() -> None:
    html = """
    <table class="xxgk_table_wza">
      <tr><th>文件编号</th><td>—  —</td></tr>
    </table>
    """
    body, doc_number = WndPolicyCrawler._parse_detail(html)

    assert body == ""
    assert doc_number == ""  # 占位短横规整为空


def test_parse_publish_date_tolerates_bad_input() -> None:
    assert _parse_publish_date("2026-06-03") == date(2026, 6, 3)
    assert _parse_publish_date("") is None
    assert _parse_publish_date("不是日期") is None


def test_clean_dash_strips_placeholder() -> None:
    assert _clean_dash("—  —") == ""
    assert _clean_dash("\xa0-\xa0") == ""
    assert _clean_dash("锡政〔2026〕1号") == "锡政〔2026〕1号"


def _payload(total_pages: int, *rows: tuple) -> dict:
    """构造列表接口 JSON fixture：rows=(url, title, writeTime) 三元组。"""
    return {"data": {"totalPages": total_pages, "data": [
        {"url": u, "title": t, "writeTime": d} for (u, t, d) in rows
    ]}}


def test_crawl_contest_mode_skips_stale_and_result_notices() -> None:
    """赛事模式(时效窗口+排除词)：过旧/获奖公示类条目在详情抓取前跳过；
    列表按时间倒序，整页过旧提前停止翻页。"""
    import asyncio
    from datetime import timedelta

    today = date.today()
    fresh = (today - timedelta(days=30)).isoformat()
    stale = (today - timedelta(days=400)).isoformat()
    pages = {
        1: _payload(3,
                    ("u1", "关于举办2026创新创业大赛的通知", fresh),
                    ("u2", "关于公布大赛获奖名单的通知", fresh),
                    ("u3", "关于举办2024大赛的通知", stale)),
        2: _payload(3, ("u4", "关于举办2023大赛的通知", stale)),  # 整页过旧
        3: _payload(3, ("u5", "不应被抓到的大赛", fresh)),
    }
    crawler = WndPolicyCrawler(
        request_delay=0, title_keyword="大赛", source="wnd-contest",
        max_age_days=180, title_exclude=("获奖", "公示", "公布", "名单", "结果"),
    )
    fetched: list = []
    enriched: list = []

    async def fake_fetch_list(client, page):
        fetched.append(page)
        return pages.get(page)

    async def fake_enrich(client, policy):
        enriched.append(policy.source_url)
        policy.body_text = "正文"

    crawler._fetch_list = fake_fetch_list  # type: ignore[method-assign]
    crawler._enrich_detail = fake_enrich  # type: ignore[method-assign]

    policies = asyncio.run(crawler.crawl(max_pages=3))

    assert [p.source_url for p in policies] == ["u1"]
    assert enriched == ["u1"]  # 过滤发生在详情抓取之前(省详情/LLM/向量开销)
    assert fetched == [1, 2]  # 第2页整页过旧 → 不再翻第3页
