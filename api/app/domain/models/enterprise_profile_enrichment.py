"""企业档案联网增强(①b)结果模型 —— 逐字段带来源。

承载「AI 联网补全」经 agentic 研究(浏览器+搜索多步)得到的**建议字段**，每个字段
携带其证据来源 URL(天眼查/企查查/官网等)，供前端回填表单并在字段旁展示引用，由用户
审阅修改后再走现有 PUT 保存。本模型不落库、不强制覆盖既有档案。
"""

from typing import List

from pydantic import BaseModel, Field

from app.domain.models.enterprise_profile import EnterpriseScale


class EnrichedField(BaseModel):
    """单值增强字段：建议值 + 证据来源URL"""
    value: str = ""  # 建议值(scale 为枚举字符串)
    source: str = ""  # 该字段证据来源URL(空表示无确切来源)


class EnrichedTags(BaseModel):
    """标签型增强字段：建议值列表 + 证据来源URL"""
    values: List[str] = Field(default_factory=list)
    source: str = ""


class EnterpriseProfileEnrichment(BaseModel):
    """企业档案联网增强建议(逐字段带来源，不落库)"""
    industry: EnrichedField = Field(default_factory=EnrichedField)  # 建议行业
    scale: EnrichedField = Field(default_factory=EnrichedField)  # 建议规模(value 为枚举值)
    main_business: EnrichedField = Field(default_factory=EnrichedField)  # 建议主营业务
    qualifications: EnrichedTags = Field(default_factory=EnrichedTags)  # 建议资质
    tech_domains: EnrichedTags = Field(default_factory=EnrichedTags)  # 建议技术/产品领域
    keywords: EnrichedTags = Field(default_factory=EnrichedTags)  # 建议关键词
    sources: List[str] = Field(default_factory=list)  # 研究中实际访问过的全部来源URL
    note: str = ""  # 给用户的说明(如未研究出结果时的提示)

    @staticmethod
    def coerce_scale(value: str) -> str:
        """将抽取出的规模值安全映射到合法枚举值，非法回落 unspecified"""
        try:
            return EnterpriseScale(value).value
        except (ValueError, KeyError):
            return EnterpriseScale.UNSPECIFIED.value
