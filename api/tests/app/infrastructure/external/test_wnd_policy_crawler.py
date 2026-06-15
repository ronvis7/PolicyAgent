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
