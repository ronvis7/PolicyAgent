"""ProfileEnrichmentService 离线单元测试：企业档案联网增强(①b)。

用 fake LLM / SearchEngine / JSONParser 隔离外部依赖，验证「联网搜索 → LLM 抽取 →
映射为建议字段」链路及各类降级路径。异步方法用 asyncio.run 驱动(与本仓库其他测试一致)。
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from app.application.services.profile_enrichment_service import ProfileEnrichmentService
from app.domain.models.enterprise_profile import EnterpriseScale
from app.domain.models.search import SearchResultItem, SearchResults
from app.domain.models.tool_result import ToolResult


class FakeSearchEngine:
    """可配置返回结果或失败的搜索引擎假实现，并记录最后一次查询。"""

    def __init__(self, items: Optional[List[SearchResultItem]] = None, success: bool = True) -> None:
        self._items = items or []
        self._success = success
        self.last_query: Optional[str] = None

    async def invoke(self, query: str, date_range: Optional[str] = None) -> ToolResult:
        self.last_query = query
        if not self._success:
            return ToolResult(success=False, message="搜索失败")
        return ToolResult(
            success=True,
            message="ok",
            data=SearchResults(query=query, total_results=len(self._items), results=self._items),
        )


class FakeLLM:
    """返回预设 content 的 LLM 假实现，并记录是否被调用。"""

    def __init__(self, content: str) -> None:
        self._content = content
        self.called = False
        self.last_response_format: Optional[Dict[str, Any]] = None

    async def invoke(self, messages, tools=None, response_format=None, tool_choice=None) -> Dict[str, Any]:
        self.called = True
        self.last_response_format = response_format
        return {"role": "assistant", "content": self._content, "tool_calls": None}

    @property
    def model_name(self) -> str:
        return "fake"

    @property
    def temperature(self) -> float:
        return 0.0

    @property
    def max_tokens(self) -> int:
        return 1024


class FakeJSONParser:
    """容错 JSON 解析器假实现：解析失败时返回 default_value。"""

    async def invoke(self, text: str, default_value: Any = None):
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return default_value


_ITEMS = [
    SearchResultItem(url="https://a.com", title="无锡某智能制造", snippet="工业机器人研发"),
    SearchResultItem(url="https://b.com", title="高新技术企业公示", snippet="国家高新技术企业"),
]

_LLM_JSON = json.dumps({
    "industry": "智能制造",
    "scale": "small",
    "main_business": "工业机器人研发与系统集成",
    "qualifications": ["高新技术企业", "专精特新"],
    "tech_domains": ["工业机器人", "机器视觉"],
    "keywords": ["智能制造", "自动化"],
}, ensure_ascii=False)


def _service(search: FakeSearchEngine, llm: FakeLLM) -> ProfileEnrichmentService:
    return ProfileEnrichmentService(llm=llm, search_engine=search, json_parser=FakeJSONParser())


def test_enrich_extracts_fields_from_search_and_llm() -> None:
    """正常链路：从搜索摘要 + LLM 抽取出结构化建议字段"""
    search = FakeSearchEngine(items=_ITEMS)
    llm = FakeLLM(_LLM_JSON)

    result = asyncio.run(_service(search, llm).enrich("无锡某智能制造有限公司"))

    assert result.industry == "智能制造"
    assert result.scale is EnterpriseScale.SMALL
    assert result.main_business == "工业机器人研发与系统集成"
    assert result.qualifications == ["高新技术企业", "专精特新"]
    assert result.tech_domains == ["工业机器人", "机器视觉"]
    assert result.keywords == ["智能制造", "自动化"]
    assert llm.last_response_format == {"type": "json_object"}


def test_enrich_sources_come_from_search_results() -> None:
    """来源URL取自搜索命中条目，供用户核验"""
    search = FakeSearchEngine(items=_ITEMS)
    result = asyncio.run(_service(search, FakeLLM(_LLM_JSON)).enrich("无锡某智能制造"))

    assert result.sources == ["https://a.com", "https://b.com"]


def test_enrich_empty_company_name_skips_search_and_llm() -> None:
    """企业名为空时直接返回提示，不调用搜索与 LLM"""
    search = FakeSearchEngine(items=_ITEMS)
    llm = FakeLLM(_LLM_JSON)

    result = asyncio.run(_service(search, llm).enrich("   "))

    assert result.industry == ""
    assert result.note != ""
    assert search.last_query is None
    assert llm.called is False


def test_enrich_no_search_results_returns_note_without_llm() -> None:
    """搜索无结果时给出提示并跳过 LLM(无证据不臆造)"""
    search = FakeSearchEngine(items=[])
    llm = FakeLLM(_LLM_JSON)

    result = asyncio.run(_service(search, llm).enrich("查无此企业"))

    assert result.note != ""
    assert result.industry == ""
    assert llm.called is False


def test_enrich_search_failure_returns_note_without_llm() -> None:
    """搜索引擎失败时降级为提示，不调用 LLM"""
    search = FakeSearchEngine(success=False)
    llm = FakeLLM(_LLM_JSON)

    result = asyncio.run(_service(search, llm).enrich("某企业"))

    assert result.note != ""
    assert llm.called is False


def test_enrich_tolerates_malformed_llm_json() -> None:
    """LLM 返回非 JSON 时容错为空建议(仍带来源)，不抛异常"""
    search = FakeSearchEngine(items=_ITEMS)
    result = asyncio.run(_service(search, FakeLLM("抱歉我无法回答")).enrich("某企业"))

    assert result.industry == ""
    assert result.qualifications == []
    assert result.sources == ["https://a.com", "https://b.com"]


def test_enrich_coerces_unknown_scale_to_unspecified() -> None:
    """LLM 给出非法规模值时安全回落为 UNSPECIFIED"""
    bad = json.dumps({"industry": "X", "scale": "巨型企业"}, ensure_ascii=False)
    search = FakeSearchEngine(items=_ITEMS)

    result = asyncio.run(_service(search, FakeLLM(bad)).enrich("某企业"))

    assert result.scale is EnterpriseScale.UNSPECIFIED
    assert result.industry == "X"


def test_enrich_cleans_and_dedupes_tag_lists() -> None:
    """资质/技术域/关键词去空去重，防止 LLM 给出脏数据"""
    dirty = json.dumps({
        "qualifications": ["高新技术企业", " 高新技术企业 ", "", "专精特新"],
        "keywords": ["a", "a", "b"],
    }, ensure_ascii=False)
    search = FakeSearchEngine(items=_ITEMS)

    result = asyncio.run(_service(search, FakeLLM(dirty)).enrich("某企业"))

    assert result.qualifications == ["高新技术企业", "专精特新"]
    assert result.keywords == ["a", "b"]
