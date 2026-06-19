"""keyword_extractor 纯函数单测：从自述文本抽候选关键词、过滤停用词/已填项。"""

from app.domain.services.keyword_extractor import suggest_keywords


def test_empty_text_returns_empty() -> None:
    assert suggest_keywords("") == []
    assert suggest_keywords("   ") == []


def test_extracts_domain_terms_from_business_text() -> None:
    text = "公司专注于集成电路设计与半导体封装测试，提供车规级芯片解决方案。"
    tags = suggest_keywords(text, top_k=10)
    # 至少抽到领域性词；停用词(公司/提供/解决方案)不应出现
    assert any(t in tags for t in ("集成电路", "半导体", "芯片", "封装"))
    assert "公司" not in tags and "提供" not in tags


def test_excludes_already_filled_terms() -> None:
    text = "主营工业机器人与自动化产线集成，深耕智能制造。"
    first = suggest_keywords(text, top_k=10)
    assert first, "应能抽到候选词"
    # 把已抽到的第一个词作为已填项排除，结果里不应再出现它
    again = suggest_keywords(text, exclude=[first[0]], top_k=10)
    assert first[0] not in again


def test_respects_top_k_and_dedup() -> None:
    text = "新能源 新能源 锂电池 储能 光伏 充电桩 电控 电机 整车 智能网联 车联网 自动驾驶"
    tags = suggest_keywords(text, top_k=5)
    assert len(tags) <= 5
    assert len(tags) == len(set(tags))  # 去重


def test_filters_short_and_stopwords() -> None:
    tags = suggest_keywords("企业管理与政策支持服务", top_k=10)
    assert all(len(t) >= 2 for t in tags)
    assert "企业" not in tags and "政策" not in tags
