"""GxtPolicyCrawler 纯解析单元测试：不触网，用真实接口/页面结构的 fixture 驱动。"""

import asyncio
from datetime import date

from app.infrastructure.external.crawler.gxt_policy_crawler import (
    GxtPolicyCrawler,
    _absolute_url,
    _clean_dash,
    _parse_publish_date,
)

# dataproxy /module/web/jpage/dataproxy.jsp 的真实返回结构(节选)：
# <totalrecord>/<totalpage> + 每条 <record><![CDATA[ <li><a href title>标题</a><span>日期</span></li> ]]>
_LIST_XML = """<datastore><totalrecord>940</totalrecord><totalpage>63</totalpage><recordset>
<record><![CDATA[ <li class="ft14lh30 cf"><font> · </font>
<a href="/art/2026/6/10/art_6278_11783480.html" target="_blank" title="关于印发江苏省“人工智能+制造”实施方案的通知">关于印发江苏省“人工智能+制造”实施方案的通知</a>
<span>2026-06-10</span></li> ]]></record>
<record><![CDATA[ <li class="ft14lh30 cf"><font> · </font>
<a href="/art/2026/5/18/art_6278_11772533.html" target="_blank" title="省工业和信息化厅关于组织申报2026年度专精特新中小企业的通知">省工业和信息化厅关于组织申报2026年度专精特新中小企业的通知</a>
<span>2026-05-18</span></li> ]]></record>
<record><![CDATA[ <li><font> · </font><span>无链接脏数据</span></li> ]]></record>
</recordset></datastore>"""

# 详情页真实结构(节选)：正文在 div.article_zoom；文件通知多无结构化文号表，文号尽力而为
_DETAIL_HTML = """
<div id="con1" class="con912">
  <div class="article_zoom">
    <p>各设区市工业和信息化主管部门：现将有关申报事项通知如下。</p>
    <p>一、申报条件……。二、申报材料于2026年7月31日前报送。</p>
  </div>
</div>
"""

_DETAIL_WITH_DOCNUM = """
<div class="article_zoom">
  <p>发文字号：苏工信中小企业〔2026〕123号</p>
  <p>正文内容。</p>
</div>
"""


def test_parse_list_payload_maps_fields_and_skips_no_link() -> None:
    policies = GxtPolicyCrawler._parse_list_payload(_LIST_XML)

    assert len(policies) == 2  # 无 <a> 的脏记录被跳过
    p = policies[0]
    assert p.source == "gxt"
    assert p.source_url == "https://gxt.jiangsu.gov.cn/art/2026/6/10/art_6278_11783480.html"
    assert p.title.startswith("关于印发江苏省")
    assert p.publish_date == date(2026, 6, 10)
    assert p.region == "江苏省"
    assert p.body_text == ""  # 正文由详情页补全


def test_parse_list_payload_uses_given_source() -> None:
    policies = GxtPolicyCrawler._parse_list_payload(_LIST_XML, source="gxt-custom")
    assert policies[0].source == "gxt-custom"
    assert policies[0].region == "江苏省"  # 同门户地区不变


def test_parse_list_payload_filters_by_title_keyword() -> None:
    """传 title_keyword 只保留标题命中的条目(留作按'申报'等聚焦栏目子集)。"""
    policies = GxtPolicyCrawler._parse_list_payload(_LIST_XML, title_keyword="申报")

    assert len(policies) == 1
    assert "申报" in policies[0].title


def test_total_pages_computed_from_totalrecord() -> None:
    """页数按 <totalrecord> 与当前 page_size 自算(不信任接口 totalpage)。"""
    crawler = GxtPolicyCrawler(page_size=15)
    assert crawler._total_pages(_LIST_XML) == 63  # ceil(940/15)
    assert GxtPolicyCrawler(page_size=20)._total_pages(_LIST_XML) == 47  # ceil(940/20)
    assert crawler._total_pages("<datastore></datastore>") == 0


def test_fetch_list_sends_pagination_params() -> None:
    crawler = GxtPolicyCrawler(page_size=15, column_id=6278)
    sent = {}

    class _Resp:
        text = _LIST_XML
        def raise_for_status(self): ...

    class _Client:
        async def get(self, url, params=None, headers=None):
            sent["url"] = url
            sent["params"] = params
            return _Resp()

    xml = asyncio.run(crawler._fetch_list(_Client(), 2))
    assert xml == _LIST_XML
    assert sent["params"]["columnid"] == 6278
    assert sent["params"]["startrecord"] == 16  # 第2页(每页15) → 16..30
    assert sent["params"]["endrecord"] == 30


def test_parse_detail_extracts_body_from_article_zoom() -> None:
    body, doc_number = GxtPolicyCrawler._parse_detail(_DETAIL_HTML)

    assert "申报条件" in body and "2026年7月31日" in body
    assert doc_number == ""  # 该通知无文号表


def test_parse_detail_best_effort_doc_number() -> None:
    body, doc_number = GxtPolicyCrawler._parse_detail(_DETAIL_WITH_DOCNUM)
    assert doc_number == "苏工信中小企业〔2026〕123号"


def test_parse_detail_handles_missing_body() -> None:
    body, doc_number = GxtPolicyCrawler._parse_detail("<div>无正文容器</div>")
    assert body == ""
    assert doc_number == ""


def test_absolute_url_prefixes_relative_paths() -> None:
    assert _absolute_url("/art/2026/6/10/art_6278_1.html") == "https://gxt.jiangsu.gov.cn/art/2026/6/10/art_6278_1.html"
    assert _absolute_url("https://x/y.html") == "https://x/y.html"
    assert _absolute_url("") == ""


def test_parse_publish_date_tolerates_bad_input() -> None:
    assert _parse_publish_date("2026-06-10") == date(2026, 6, 10)
    assert _parse_publish_date("") is None
    assert _parse_publish_date("不是日期") is None


def test_clean_dash_strips_placeholder() -> None:
    assert _clean_dash("—  —") == ""
    assert _clean_dash("苏工信〔2026〕1号") == "苏工信〔2026〕1号"
