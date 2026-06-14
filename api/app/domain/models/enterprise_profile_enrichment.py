"""企业档案联网增强(①b)结果模型。

承载「AI 联网补全」从公开网络检索 + LLM 抽取得到的**建议字段**，供前端回填表单
由用户审阅修改后再走现有 PUT 保存。本模型不落库、不强制覆盖既有档案，仅作建议载体；
字段集与 EnterpriseProfile 的可增强部分对齐(不含企业名/地区等用户主导的标识字段)。
"""

from typing import List

from pydantic import BaseModel, Field

from app.domain.models.enterprise_profile import EnterpriseScale


class EnterpriseProfileEnrichment(BaseModel):
    """企业档案联网增强建议(不落库，仅供前端回填审阅)"""
    industry: str = ""  # 建议行业
    scale: EnterpriseScale = EnterpriseScale.UNSPECIFIED  # 建议规模
    main_business: str = ""  # 建议主营业务简介
    qualifications: List[str] = Field(default_factory=list)  # 建议资质
    tech_domains: List[str] = Field(default_factory=list)  # 建议技术/产品领域
    keywords: List[str] = Field(default_factory=list)  # 建议关键词
    sources: List[str] = Field(default_factory=list)  # 证据来源URL(供用户核验)
    note: str = ""  # 给用户的说明(如未检索到公开信息时的提示)
