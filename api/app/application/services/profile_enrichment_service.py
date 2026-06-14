"""企业档案联网增强服务(①b)：agentic 研究 + 逐字段带来源抽取。

与聊天同源的能力路线——给 LLM 配上**搜索 + 浏览器**工具，让它多步研究目标企业
(优先天眼查/企查查/官网)，再做一次结构化抽取，产出每个字段的建议值 **及其来源 URL**，
供前端回填表单并在字段旁展示引用，由用户审阅修改后再走现有 PUT 保存。本服务不落库。

设计：自包含的轻量 ReAct 循环(复用真实 SearchTool/BrowserTool + 一次性沙箱)，不背
session/redis/SSE 那套聊天机器；沙箱用完即销毁。外部依赖全部注入，便于以 fake 沙箱/LLM
离线测试循环逻辑。
"""

import logging
from typing import Any, Dict, List, Optional, Type

from app.domain.external.json_parser import JSONParser
from app.domain.external.llm import LLM
from app.domain.external.sandbox import Sandbox
from app.domain.external.search import SearchEngine
from app.domain.models.enterprise_profile_enrichment import (
    EnrichedField,
    EnrichedTags,
    EnterpriseProfileEnrichment,
)
from app.domain.services.tools.browser import BrowserTool
from app.domain.services.tools.search import SearchTool

logger = logging.getLogger(__name__)

# 研究循环参数
_MAX_STEPS = 8  # 最多工具调用轮数(控制时长与成本)
_TOOL_RESULT_CHAR_LIMIT = 4000  # 单次工具结果喂回 LLM 的截断上限
_MAX_SOURCES = 12  # 返回给前端的来源 URL 上限
_MAX_TAG = 64
_MAX_TAGS = 50

# 仅放开研究所需工具子集(避免 LLM 误用文件/沙箱等无关工具)
_ALLOWED_TOOLS = {"search_web", "browser_navigate", "browser_view", "browser_scroll_down"}

_RESEARCH_SYSTEM_PROMPT = (
    "你是企业情报研究员。用户会给出一家企业名称(及地区)，请用搜索与浏览器工具联网研究该企业，"
    "目标是为其建立结构化档案以做政策申报匹配。要求：\n"
    "1. 优先访问权威来源：天眼查、企查查、爱企查、国家企业信用信息公示系统、企业官网、政府公示页。\n"
    "2. 先 search_web 找到候选页面，再用 browser_navigate 打开、browser_view 阅读核心信息，必要时 scroll。\n"
    "3. 聚焦：所属行业、企业规模、主营业务、已有资质(高新技术企业/专精特新等)、技术或产品领域、关键词。\n"
    "4. 记住你访问过的每条信息来自哪个网址，后续要逐字段标注来源。\n"
    "5. 信息足够后，停止调用工具，直接用文字总结你的发现(含来源网址)。找不到就如实说明。"
)

_EXTRACTION_INSTRUCTION = (
    "基于以上研究，输出企业结构化档案建议。只返回一个 JSON 对象，键如下，每个字段附其证据来源网址 source"
    "(取你实际访问过的页面URL)；没有把握的字段留空(value 用\"\"，values 用[]，source 用\"\")，"
    "禁止编造：\n"
    '{\n'
    '  "industry": {"value": "所属行业", "source": "url"},\n'
    '  "scale": {"value": "micro|small|medium|large 之一，无法判断留空", "source": "url"},\n'
    '  "main_business": {"value": "主营业务简介", "source": "url"},\n'
    '  "qualifications": {"values": ["资质1"], "source": "url"},\n'
    '  "tech_domains": {"values": ["领域1"], "source": "url"},\n'
    '  "keywords": {"values": ["关键词1"], "source": "url"}\n'
    '}'
)


class ProfileEnrichmentService:
    """企业档案联网增强服务(agentic 研究，逐字段带来源，不落库)"""

    def __init__(
        self,
        llm: LLM,
        sandbox_cls: Type[Sandbox],
        search_engine: SearchEngine,
        json_parser: JSONParser,
        max_steps: int = _MAX_STEPS,
    ) -> None:
        self._llm = llm
        self._sandbox_cls = sandbox_cls
        self._search_engine = search_engine
        self._json_parser = json_parser
        self._max_steps = max_steps
        self._messages: List[Dict[str, Any]] = []

    async def enrich(
        self,
        company_name: str,
        province: str = "",
        city: str = "",
        district: str = "",
    ) -> EnterpriseProfileEnrichment:
        """联网研究企业并抽取逐字段带来源的建议。

        无企业名直接返回提示；研究失败(如沙箱不可用)降级为带 note 的空建议，不抛 500。
        """
        company_name = (company_name or "").strip()
        if not company_name:
            return EnterpriseProfileEnrichment(note="请先填写企业名称再使用联网补全")

        region = "".join(p for p in (province, city, district) if p).strip()
        sandbox: Optional[Sandbox] = None
        try:
            sandbox = await self._sandbox_cls.create()
            browser = await sandbox.get_browser()
            if not browser:
                return EnterpriseProfileEnrichment(note="联网研究环境暂不可用(浏览器未就绪)，请稍后重试或手动填写")

            search_tool = SearchTool(search_engine=self._search_engine)
            browser_tool = BrowserTool(browser=browser)
            visited = await self._run_research(company_name, region, search_tool, browser_tool)
            parsed = await self._extract_structured()
            return self._build_enrichment(parsed, visited)
        except Exception as e:  # 沙箱/浏览器/网络等失败统一降级，不向用户抛 500
            reason = f"{type(e).__name__}: {str(e) or '未知错误'}"
            logger.exception(f"企业档案联网研究失败[{company_name}]: {reason}")
            return EnterpriseProfileEnrichment(note=f"联网研究失败（{reason[:300]}），请稍后重试或手动填写档案")
        finally:
            if sandbox is not None:
                try:
                    await sandbox.destroy()
                except Exception:
                    logger.warning("销毁研究沙箱失败(忽略)")

    # ---------- 研究循环 ----------

    async def _run_research(
        self, company_name: str, region: str, search_tool: SearchTool, browser_tool: BrowserTool,
    ) -> List[str]:
        """驱动 LLM 多步调用搜索/浏览器研究企业，返回访问过的来源URL列表。

        研究过程产生的消息累积在 self._messages，供后续抽取复用。
        """
        schemas = self._allowed_schemas(search_tool, browser_tool)
        tool_map = {"search_web": search_tool, "browser_navigate": browser_tool,
                    "browser_view": browser_tool, "browser_scroll_down": browser_tool}

        self._messages = [
            {"role": "system", "content": _RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": f"请研究企业：{company_name}\n地区：{region or '未知'}"},
        ]
        visited: List[str] = []

        for _ in range(self._max_steps):
            message = await self._llm.invoke(self._messages, tools=schemas, tool_choice="auto")
            tool_calls = (message or {}).get("tool_calls") or []
            # 记录助手消息(一次只处理一个工具调用，对齐既有 ReAct 约定)
            assistant: Dict[str, Any] = {"role": "assistant", "content": (message or {}).get("content") or ""}
            if not tool_calls:
                self._messages.append(assistant)
                break
            call = tool_calls[0]
            assistant["tool_calls"] = [call]
            self._messages.append(assistant)

            name = (call.get("function") or {}).get("name", "")
            args = await self._json_parser.invoke(
                (call.get("function") or {}).get("arguments") or "{}", default_value={}
            )
            if not isinstance(args, dict):
                args = {}

            content = await self._call_tool(tool_map, name, args, visited)
            self._messages.append({
                "role": "tool",
                "tool_call_id": call.get("id") or name,
                "content": content[:_TOOL_RESULT_CHAR_LIMIT],
            })

        return self._dedupe(visited)[:_MAX_SOURCES]

    async def _call_tool(
        self, tool_map: Dict[str, Any], name: str, args: Dict[str, Any], visited: List[str],
    ) -> str:
        """执行单次工具调用，顺带收集来源URL；未知/失败工具返回提示文本喂回 LLM"""
        tool = tool_map.get(name)
        if tool is None:
            return f"工具[{name}]不可用，请改用 search_web 或 browser_navigate。"

        if name == "browser_navigate" and isinstance(args.get("url"), str):
            visited.append(args["url"])

        try:
            result = await tool.invoke(name, **args)
        except Exception as e:
            return f"工具调用出错: {type(e).__name__}: {e}"

        # 搜索结果顺带收集候选来源URL
        data = getattr(result, "data", None)
        if name == "search_web" and data is not None:
            for item in getattr(data, "results", []) or []:
                if getattr(item, "url", ""):
                    visited.append(item.url)

        return self._serialize_result(result)

    # ---------- 结构化抽取 ----------

    async def _extract_structured(self) -> Dict[str, Any]:
        """在研究上下文后追加抽取指令，要求 LLM 产出逐字段带来源的 JSON"""
        messages = self._messages + [{"role": "user", "content": _EXTRACTION_INSTRUCTION}]
        message = await self._llm.invoke(messages, response_format={"type": "json_object"})
        parsed = await self._json_parser.invoke((message or {}).get("content") or "", default_value={})
        return parsed if isinstance(parsed, dict) else {}

    def _build_enrichment(self, parsed: Dict[str, Any], visited: List[str]) -> EnterpriseProfileEnrichment:
        """将抽取 JSON 映射为逐字段带来源的增强模型(防御性清洗)"""
        scale = self._field(parsed.get("scale"))
        scale.value = EnterpriseProfileEnrichment.coerce_scale(scale.value)
        return EnterpriseProfileEnrichment(
            industry=self._field(parsed.get("industry")),
            scale=scale,
            main_business=self._field(parsed.get("main_business")),
            qualifications=self._tags(parsed.get("qualifications")),
            tech_domains=self._tags(parsed.get("tech_domains")),
            keywords=self._tags(parsed.get("keywords")),
            sources=visited,
        )

    # ---------- 工具/清洗辅助 ----------

    @staticmethod
    def _allowed_schemas(*tools: Any) -> List[Dict[str, Any]]:
        """仅取放开工具子集的 schema 喂给 LLM"""
        schemas = []
        for tool in tools:
            for schema in tool.get_tools():
                if schema.get("function", {}).get("name") in _ALLOWED_TOOLS:
                    schemas.append(schema)
        return schemas

    @staticmethod
    def _serialize_result(result: Any) -> str:
        """将工具结果转为喂回 LLM 的文本(优先结构化 data，回落 message)"""
        data = getattr(result, "data", None)
        if data is not None:
            try:
                return data.model_dump_json(exclude_none=True)
            except Exception:
                return str(data)
        return getattr(result, "message", "") or ""

    @staticmethod
    def _field(raw: Any) -> EnrichedField:
        """解析单值字段 {value, source}，容错非字典/缺键"""
        if not isinstance(raw, dict):
            return EnrichedField()
        value = raw.get("value")
        source = raw.get("source")
        return EnrichedField(
            value=value.strip() if isinstance(value, str) else "",
            source=source.strip() if isinstance(source, str) else "",
        )

    @classmethod
    def _tags(cls, raw: Any) -> EnrichedTags:
        """解析标签字段 {values, source}，去空去重限长"""
        if not isinstance(raw, dict):
            return EnrichedTags()
        source = raw.get("source")
        return EnrichedTags(
            values=cls._clean_tags(raw.get("values")),
            source=source.strip() if isinstance(source, str) else "",
        )

    @staticmethod
    def _clean_tags(values: Any) -> List[str]:
        """去空白、丢空值、按序去重，限制单标签长度与数量"""
        if not isinstance(values, list):
            return []
        seen: set = set()
        cleaned: List[str] = []
        for raw in values:
            tag = raw.strip()[:_MAX_TAG] if isinstance(raw, str) else ""
            if tag and tag not in seen:
                seen.add(tag)
                cleaned.append(tag)
        return cleaned[:_MAX_TAGS]

    @staticmethod
    def _dedupe(urls: List[str]) -> List[str]:
        """按序去重URL"""
        seen: set = set()
        out: List[str] = []
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out
