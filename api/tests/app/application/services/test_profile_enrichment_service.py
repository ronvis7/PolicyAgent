"""ProfileEnrichmentService(agentic 研究)离线单元测试。

用 fake 沙箱/浏览器/搜索/LLM 驱动 ReAct 研究循环 + 逐字段抽取，不触网、不依赖 docker。
异步方法用 asyncio.run 驱动(与本仓库其他测试一致)。
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from app.application.services.profile_enrichment_service import ProfileEnrichmentService
from app.domain.models.search import SearchResultItem, SearchResults
from app.domain.models.tool_result import ToolResult


# ---------- fakes ----------

class FakeBrowser:
    """浏览器假实现：导航/查看返回固定页面文本(ToolResult.message)。"""
    async def navigate(self, url: str) -> ToolResult:
        return ToolResult(success=True, message=f"已打开 {url}")

    async def view_page(self) -> ToolResult:
        return ToolResult(success=True, message="页面：无锡比邻星科技，主营卫星通信终端，国家高新技术企业。")

    async def scroll_down(self, to_bottom: Optional[bool] = None) -> ToolResult:
        return ToolResult(success=True, message="(已向下滚动)")


class FakeSandbox:
    """沙箱假实现：记录创建/销毁，可配置 browser 是否就绪。"""
    instances: List["FakeSandbox"] = []
    browser_ready: bool = True

    def __init__(self) -> None:
        self.destroyed = False

    @classmethod
    async def create(cls) -> "FakeSandbox":
        inst = cls()
        cls.instances.append(inst)
        return inst

    async def get_browser(self):
        return FakeBrowser() if FakeSandbox.browser_ready else None

    async def destroy(self) -> bool:
        self.destroyed = True
        return True


class FakeSearchEngine:
    def __init__(self, items: Optional[List[SearchResultItem]] = None) -> None:
        self._items = items or [
            SearchResultItem(url="https://www.tianyancha.com/company/123", title="无锡比邻星科技-天眼查", snippet="卫星通信"),
        ]

    async def invoke(self, query: str, date_range: Optional[str] = None) -> ToolResult:
        return ToolResult(success=True, message="ok",
                          data=SearchResults(query=query, results=self._items))


class FakeLLM:
    """按脚本依次返回消息的 LLM；记录调用次数与每次收到的消息(深拷贝)。"""
    def __init__(self, scripted: List[Dict[str, Any]]) -> None:
        self._scripted = list(scripted)
        self.calls = 0
        self.received: List[List[Dict[str, Any]]] = []

    async def invoke(self, messages, tools=None, response_format=None, tool_choice=None) -> Dict[str, Any]:
        self.calls += 1
        self.received.append([dict(m) for m in messages])
        return self._scripted.pop(0) if self._scripted else {"role": "assistant", "content": "{}"}

    @property
    def model_name(self) -> str: return "fake"
    @property
    def temperature(self) -> float: return 0.0
    @property
    def max_tokens(self) -> int: return 1024


class FakeJSONParser:
    async def invoke(self, text: str, default_value: Any = None):
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return default_value


def _tool_call(name: str, args: dict, cid: str = "c1") -> Dict[str, Any]:
    return {"role": "assistant", "content": "",
            "tool_calls": [{"id": cid, "function": {"name": name, "arguments": json.dumps(args)}}]}


_EXTRACTION = json.dumps({
    "industry": {"value": "卫星通信", "source": "https://www.tianyancha.com/company/123"},
    "scale": {"value": "small", "source": "https://www.tianyancha.com/company/123"},
    "main_business": {"value": "卫星通信终端研发", "source": "https://bilinxing.com"},
    "qualifications": {"values": ["高新技术企业", "高新技术企业", " "], "source": "https://gov.cn/pub"},
    "tech_domains": {"values": ["卫星通信"], "source": ""},
    "keywords": {"values": ["卫星", "通信"], "source": ""},
}, ensure_ascii=False)


def _service(llm: FakeLLM, search: Optional[FakeSearchEngine] = None, max_steps: int = 8) -> ProfileEnrichmentService:
    return ProfileEnrichmentService(
        llm=llm, sandbox_cls=FakeSandbox,
        search_engine=search or FakeSearchEngine(), json_parser=FakeJSONParser(),
        max_steps=max_steps,
    )


def setup_function() -> None:
    FakeSandbox.instances = []
    FakeSandbox.browser_ready = True


# ---------- tests ----------

def test_research_then_extract_per_field_with_sources() -> None:
    """研究(搜索)→结束→抽取，得到逐字段值与来源，scale 合法、标签去重"""
    llm = FakeLLM([
        _tool_call("search_web", {"query": "无锡比邻星科技"}),
        {"role": "assistant", "content": "已找到天眼查信息"},  # 无 tool_calls → 结束研究
        {"role": "assistant", "content": _EXTRACTION},  # 抽取
    ])
    result = asyncio.run(_service(llm).enrich("无锡比邻星科技有限公司"))

    assert result.industry.value == "卫星通信"
    assert result.industry.source == "https://www.tianyancha.com/company/123"
    assert result.scale.value == "small"
    assert result.main_business.value == "卫星通信终端研发"
    assert result.qualifications.values == ["高新技术企业"]  # 去重去空
    assert result.qualifications.source == "https://gov.cn/pub"
    assert result.keywords.values == ["卫星", "通信"]
    assert "https://www.tianyancha.com/company/123" in result.sources


def test_browser_navigate_url_collected_as_source() -> None:
    """LLM 用 browser_navigate 打开的页面进入来源列表"""
    llm = FakeLLM([
        _tool_call("browser_navigate", {"url": "https://bilinxing.com/about"}),
        {"role": "assistant", "content": "看完官网"},
        {"role": "assistant", "content": _EXTRACTION},
    ])
    result = asyncio.run(_service(llm).enrich("无锡比邻星科技有限公司"))
    assert "https://bilinxing.com/about" in result.sources


def test_sandbox_created_and_destroyed() -> None:
    """研究用的一次性沙箱用完即销毁"""
    llm = FakeLLM([{"role": "assistant", "content": "无需工具"}, {"role": "assistant", "content": _EXTRACTION}])
    asyncio.run(_service(llm).enrich("某公司"))
    assert len(FakeSandbox.instances) == 1
    assert FakeSandbox.instances[0].destroyed is True


def test_empty_company_name_skips_sandbox() -> None:
    """空企业名直接返回提示，不创建沙箱、不调用 LLM"""
    llm = FakeLLM([])
    result = asyncio.run(_service(llm).enrich("   "))
    assert result.note != ""
    assert FakeSandbox.instances == []
    assert llm.calls == 0


def test_browser_unavailable_returns_note() -> None:
    """浏览器未就绪时降级为提示，并销毁沙箱"""
    FakeSandbox.browser_ready = False
    llm = FakeLLM([{"role": "assistant", "content": _EXTRACTION}])
    result = asyncio.run(_service(llm).enrich("某公司"))
    assert result.note != ""
    assert result.industry.value == ""
    assert FakeSandbox.instances[0].destroyed is True


def test_tolerates_malformed_extraction_json() -> None:
    """抽取返回非 JSON 时降级为空建议(不抛)，但保留研究来源"""
    llm = FakeLLM([
        _tool_call("search_web", {"query": "x"}),
        {"role": "assistant", "content": "done"},
        {"role": "assistant", "content": "抱歉无法输出"},  # 非 JSON
    ])
    result = asyncio.run(_service(llm).enrich("某公司"))
    assert result.industry.value == ""
    assert result.qualifications.values == []
    assert "https://www.tianyancha.com/company/123" in result.sources


def test_reasoning_content_passed_back_to_next_turn() -> None:
    """思考模型的 reasoning_content 必须在下一轮原样带回(否则 DeepSeek 400)"""
    llm = FakeLLM([
        {"role": "assistant", "content": "", "reasoning_content": "先查天眼查",
         "tool_calls": [{"id": "c1", "function": {"name": "search_web", "arguments": "{\"query\":\"x\"}"}}]},
        {"role": "assistant", "content": "够了"},
        {"role": "assistant", "content": _EXTRACTION},
    ])
    asyncio.run(_service(llm).enrich("某公司"))

    # 第二次调用的消息里应含带 reasoning_content 的助手消息
    second_turn_messages = llm.received[1]
    assert any(
        m.get("role") == "assistant" and m.get("reasoning_content") == "先查天眼查"
        for m in second_turn_messages
    )


def test_coerces_bad_scale_to_unspecified() -> None:
    """抽取出非法规模值时安全回落 unspecified"""
    bad = json.dumps({"scale": {"value": "巨无霸", "source": "u"}, "industry": {"value": "X"}})
    llm = FakeLLM([{"role": "assistant", "content": "no tool"}, {"role": "assistant", "content": bad}])
    result = asyncio.run(_service(llm).enrich("某公司"))
    assert result.scale.value == "unspecified"
    assert result.industry.value == "X"
