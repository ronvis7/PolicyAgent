import httpx

from app.infrastructure.external.search.bing_search import BingSearchEngine


def test_build_params_uses_chinese_market_and_encodes_date_filter_once() -> None:
    params = BingSearchEngine._build_params("创新创业大赛", "past_month")

    assert params == {
        "q": "创新创业大赛",
        "mkt": "zh-CN",
        "setlang": "zh-hans",
        "filters": 'ex1:"ez3"',
    }
    rendered = str(httpx.URL("https://www.bing.com/search", params=params))
    assert "filters=ex1%3A%22ez3%22" in rendered
    assert "%253a" not in rendered.lower()


def test_canonicalize_result_url_decodes_bing_tracking_link() -> None:
    tracking_url = "https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9leGFtcGxlLmdvdi5jbi9jb250ZXN0P3JlZj1iaW5n"

    assert BingSearchEngine._canonicalize_result_url(tracking_url) == "https://example.gov.cn/contest?ref=bing"


def test_canonicalize_result_url_rejects_invalid_tracking_target() -> None:
    assert BingSearchEngine._canonicalize_result_url("https://www.bing.com/ck/a?u=not-base64") == ""


def test_parse_rss_results_reads_bing_empty_link_element() -> None:
    content = """
    <rss><channel><item><title>上海市科技创新大赛通知</title>
    <link/>https://stcsm.sh.gov.cn/contest/1
    <description>报名参赛通知</description></item></channel></rss>
    """

    results = BingSearchEngine._parse_rss_results(content)

    assert [(result.title, result.url, result.snippet) for result in results] == [
        ("上海市科技创新大赛通知", "https://stcsm.sh.gov.cn/contest/1", "报名参赛通知"),
    ]
