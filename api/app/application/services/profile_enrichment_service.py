"""企业档案联网增强服务(①b)：联网搜索 + LLM 抽取得到结构化建议字段。

定位：以企业为主体主动服务链路的「档案首版表单 → Agent 增强」一步。给定企业名(及可选地区)，
联网检索公开信息，交 LLM 在**仅依据检索证据**的前提下抽取结构化字段，返回**建议**供前端
回填、由用户审阅修改后再走现有 PUT 落库。本服务不持久化、不直接覆盖既有档案。

设计取舍：刻意与纯 CRUD 的 EnterpriseProfileService 分离(单一职责)；外部依赖(LLM/搜索/JSON
解析)全部以协议注入，便于离线测试与替换实现。
"""

import logging
from typing import Any, Dict, List

from app.domain.external.json_parser import JSONParser
from app.domain.external.llm import LLM
from app.domain.external.search import SearchEngine
from app.domain.models.enterprise_profile import EnterpriseScale
from app.domain.models.enterprise_profile_enrichment import EnterpriseProfileEnrichment

logger = logging.getLogger(__name__)

# 喂给 LLM 的搜索摘要条数上限，控制 prompt 体积与成本
_MAX_SNIPPETS = 8
# 标签类字段单条/数量上限(与 schema 校验对齐，防 LLM 给出脏数据)
_MAX_TAG = 64
_MAX_TAGS = 50

_SYSTEM_PROMPT = (
    "你是企业情报分析助手。请仅依据用户提供的【公开网络检索结果】，抽取目标企业的结构化档案信息，"
    "用于后续政策申报条件匹配。严格遵守：\n"
    "1. 只输出能从检索结果中找到依据的信息，找不到的字段留空(字符串用\"\"，列表用[])，禁止臆造或编造。\n"
    "2. scale 必须是以下之一：unspecified/micro/small/medium/large；无法判断填 unspecified。\n"
    "3. qualifications 指已获资质(如 高新技术企业/专精特新/科技型中小企业)；tech_domains 指技术或产品领域；"
    "keywords 为 3-8 个检索价值高的关键词。\n"
    "4. 只返回 JSON 对象，键为：industry, scale, main_business, qualifications, tech_domains, keywords。"
)


class ProfileEnrichmentService:
    """企业档案联网增强服务(不落库，返回建议字段)"""

    def __init__(self, llm: LLM, search_engine: SearchEngine, json_parser: JSONParser) -> None:
        self._llm = llm
        self._search_engine = search_engine
        self._json_parser = json_parser

    async def enrich(
            self,
            company_name: str,
            province: str = "",
            city: str = "",
            district: str = "",
    ) -> EnterpriseProfileEnrichment:
        """联网检索企业公开信息并抽取结构化建议字段。

        无企业名、搜索失败或无结果时返回带提示(note)的空建议，不调用/不臆造 LLM 结果。
        """
        company_name = (company_name or "").strip()
        if not company_name:
            return EnterpriseProfileEnrichment(note="请先填写企业名称再使用联网补全")

        # 1. 联网检索(企业名 + 地区 + 引导词，提高命中政策相关公开信息的概率)
        region = "".join(p for p in (province, city, district) if p).strip()
        query = f"{company_name} {region} 主营业务 资质 高新技术".strip()
        search_result = await self._search_engine.invoke(query)

        if not search_result.success or not search_result.data or not search_result.data.results:
            return EnterpriseProfileEnrichment(
                note="未检索到该企业的公开信息，请手动填写档案",
            )

        items = search_result.data.results[:_MAX_SNIPPETS]
        sources = [item.url for item in items if item.url]

        # 2. 交 LLM 在仅依据证据的前提下抽取结构化字段
        evidence = self._format_evidence(items)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"目标企业：{company_name}\n地区：{region or '未知'}\n\n【公开网络检索结果】\n{evidence}"},
        ]
        response = await self._llm.invoke(messages, response_format={"type": "json_object"})
        content = (response or {}).get("content") or ""

        parsed = await self._json_parser.invoke(content, default_value={})
        if not isinstance(parsed, dict):
            parsed = {}

        # 3. 映射为建议(防御性清洗：规模回落、标签去空去重)
        return EnterpriseProfileEnrichment(
            industry=self._as_text(parsed.get("industry")),
            scale=self._coerce_scale(parsed.get("scale")),
            main_business=self._as_text(parsed.get("main_business")),
            qualifications=self._clean_tags(parsed.get("qualifications")),
            tech_domains=self._clean_tags(parsed.get("tech_domains")),
            keywords=self._clean_tags(parsed.get("keywords")),
            sources=sources,
        )

    @staticmethod
    def _format_evidence(items: List[Any]) -> str:
        """将搜索条目拼为编号证据块(标题 + 摘要 + 链接)供 LLM 引用"""
        lines = []
        for idx, item in enumerate(items, start=1):
            lines.append(f"[{idx}] {item.title}\n{item.snippet}\n来源: {item.url}")
        return "\n\n".join(lines)

    @staticmethod
    def _as_text(value: Any) -> str:
        """安全转字符串并裁剪空白(非字符串/None 回落为空)"""
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _coerce_scale(value: Any) -> EnterpriseScale:
        """将 LLM 给出的规模值安全映射到枚举，非法值回落 UNSPECIFIED"""
        try:
            return EnterpriseScale(value)
        except (ValueError, KeyError):
            return EnterpriseScale.UNSPECIFIED

    @staticmethod
    def _clean_tags(values: Any) -> List[str]:
        """去空白、丢空值、按序去重，限制单标签长度与数量(对齐 schema 校验)"""
        if not isinstance(values, list):
            return []
        seen: set[str] = set()
        cleaned: List[str] = []
        for raw in values:
            tag = raw.strip()[:_MAX_TAG] if isinstance(raw, str) else ""
            if tag and tag not in seen:
                seen.add(tag)
                cleaned.append(tag)
        return cleaned[:_MAX_TAGS]
