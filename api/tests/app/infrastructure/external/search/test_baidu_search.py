from app.infrastructure.external.search.baidu_search import BaiduSearchEngine


def test_build_payload_uses_v2_web_search_and_year_recency() -> None:
    engine = BaiduSearchEngine("test-key", top_k=25)

    assert engine._build_payload("人工智能 大赛 报名", "past_year") == {
        "messages": [{"role": "user", "content": "人工智能 大赛 报名"}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 25}],
        "search_recency_filter": "year",
    }


def test_parse_results_accepts_reference_content_and_deduplicates_urls() -> None:
    results = BaiduSearchEngine._parse_results({
        "references": [
            {"title": "人工智能大赛报名通知", "url": "https://example.gov.cn/a", "content": "正在报名"},
            {"title": "重复结果", "url": "https://example.gov.cn/a", "content": "重复"},
            {"title": "无效链接", "url": "javascript:alert(1)", "content": "忽略"},
        ]
    })

    assert [(row.title, row.url, row.snippet) for row in results] == [
        ("人工智能大赛报名通知", "https://example.gov.cn/a", "正在报名")
    ]


def test_top_k_is_clamped_to_api_limit() -> None:
    assert BaiduSearchEngine("test-key", top_k=100).top_k == 50
    assert BaiduSearchEngine("test-key", top_k=0).top_k == 1
