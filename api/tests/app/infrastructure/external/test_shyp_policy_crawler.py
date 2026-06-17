"""ShypPolicyCrawler 纯解析单元测试：不触网，用真实接口/页面结构的 fixture 驱动。"""

import asyncio
from datetime import date

from app.infrastructure.external.crawler.shyp_policy_crawler import (
    ShypPolicyCrawler,
    _clean_dash,
    _parse_publish_date_ms,
)

# 列表接口 /front/api/data/search 的真实返回结构(节选)
# display_date 为毫秒级 epoch；1781578594000 == 2026-06-16(UTC)
_LIST_PAYLOAD = {
    "code": 0,
    "message": "success",
    "data": {
        "pageNo": 1,
        "pageSize": 15,
        "totalPage": 98,
        "totalCount": 1463,
        "list": [
            {
                "id": "abc123",
                "title": "关于印发《关于支持打造OPC超级个体社区的若干措施》的通知",
                "display_date": 1781578594000,
                "dispatch_agency": "上海市杨浦区人民政府",
                "drafting_unit": "区科委",
                "url": "https://www.shyp.gov.cn/zhengwu/zwgk-qzfwj/2026/135/2935.html",
            },
            {  # 缺 url 的脏数据应被跳过
                "title": "无效条目",
                "url": "",
            },
        ],
    },
}

# 详情页真实结构(节选)：正文在 div#ivs_content(class=Article_content)，
# 发文字号/索引号在「标签 span + 值 span」结构里
_DETAIL_HTML = """
<div class="article-info-bz">
  <span>索引号：</span><span> YP-2026-00491 </span>
  <span>发文字号：</span><span>杨府发〔2026〕4号</span>
  <span>发文机关：</span><span>上海市杨浦区人民政府</span>
</div>
<div class="Article_content" id="ivs_content">
  <p>第一条 为支持打造OPC超级个体社区，制定本措施。</p>
  <p>第二条 本措施自发布之日起施行。</p>
</div>
"""


def test_parse_list_payload_maps_fields_and_skips_blank_url() -> None:
    policies = ShypPolicyCrawler._parse_list_payload(_LIST_PAYLOAD)

    assert len(policies) == 1  # 缺 url 的脏数据被跳过
    p = policies[0]
    assert p.source == "shyp"
    assert p.source_url == "https://www.shyp.gov.cn/zhengwu/zwgk-qzfwj/2026/135/2935.html"
    assert p.title.startswith("关于印发《关于支持打造OPC")
    assert p.issuer == "上海市杨浦区人民政府"
    assert p.publish_date == date(2026, 6, 16)
    assert p.region == "上海市杨浦区"
    assert p.body_text == ""  # 正文由详情页补全


def test_parse_list_payload_uses_given_source() -> None:
    policies = ShypPolicyCrawler._parse_list_payload(_LIST_PAYLOAD, source="shyp-custom")
    assert policies[0].source == "shyp-custom"
    assert policies[0].region == "上海市杨浦区"  # 同一门户地区不变


def test_parse_list_payload_falls_back_to_drafting_unit_for_issuer() -> None:
    payload = {
        "data": {
            "list": [
                {"title": "无发文机关", "url": "https://www.shyp.gov.cn/x.html", "drafting_unit": "区科委"}
            ]
        }
    }
    policies = ShypPolicyCrawler._parse_list_payload(payload)
    assert policies[0].issuer == "区科委"


def test_fetch_list_sends_channel_list_as_array() -> None:
    crawler = ShypPolicyCrawler(channel="1899")
    sent = {}

    class _Resp:
        def raise_for_status(self): ...
        def json(self): return _LIST_PAYLOAD

    class _Client:
        async def post(self, url, json=None, headers=None):
            sent["url"] = url
            sent["body"] = json
            return _Resp()

    asyncio.run(crawler._fetch_list(_Client(), 2))
    assert sent["body"]["channelList"] == ["1899"]  # 必须为数组
    assert sent["body"]["pageNo"] == 2


def test_total_pages_reads_pagination() -> None:
    assert ShypPolicyCrawler._total_pages(_LIST_PAYLOAD) == 98
    assert ShypPolicyCrawler._total_pages({}) == 0


def test_parse_detail_extracts_body_doc_number_and_index() -> None:
    body, doc_number, index_number = ShypPolicyCrawler._parse_detail(_DETAIL_HTML)

    assert "第一条" in body and "第二条" in body
    assert doc_number == "杨府发〔2026〕4号"
    assert index_number == "YP-2026-00491"


def test_parse_detail_handles_missing_fields() -> None:
    body, doc_number, index_number = ShypPolicyCrawler._parse_detail("<div>无正文无元数据</div>")
    assert body == ""
    assert doc_number == ""
    assert index_number == ""


def test_parse_publish_date_ms_tolerates_bad_input() -> None:
    assert _parse_publish_date_ms(1781578594000) == date(2026, 6, 16)
    assert _parse_publish_date_ms(None) is None
    assert _parse_publish_date_ms("不是时间戳") is None
    assert _parse_publish_date_ms(True) is None


def test_clean_dash_strips_placeholder() -> None:
    assert _clean_dash("—  —") == ""
    assert _clean_dash("\xa0-\xa0") == ""
    assert _clean_dash("杨府发〔2026〕4号") == "杨府发〔2026〕4号"
