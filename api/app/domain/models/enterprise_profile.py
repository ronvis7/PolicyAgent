from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class EnterpriseScale(str, Enum):
    """企业规模枚举(用于后续政策申报条件匹配)"""
    UNSPECIFIED = "unspecified"  # 未填写
    MICRO = "micro"  # 微型企业
    SMALL = "small"  # 小型企业
    MEDIUM = "medium"  # 中型企业
    LARGE = "large"  # 大型企业


class EnterpriseProfile(BaseModel):
    """企业档案领域模型，每个租户一条，承载组织级结构化信息。

    作为"以企业为主体"主动服务链路的源头：结构化字段(地区/行业/规模/资质/技术域等)
    用于后续与政策申报条件做匹配。列表型与未来增量字段在基础设施层统一以 JSONB 承载，
    本模型保持扁平、强类型。
    """
    tenant_id: str = ""  # 租户id(主键)
    company_name: str = ""  # 企业名称
    province: str = "江苏省"  # 所在省(默认无锡新吴区)
    city: str = "无锡市"  # 所在市
    district: str = "新吴区"  # 所在区/县
    industry: str = ""  # 所属行业
    scale: EnterpriseScale = EnterpriseScale.UNSPECIFIED  # 企业规模
    main_business: str = ""  # 主营业务简介
    qualifications: List[str] = Field(default_factory=list)  # 已有资质(高新/专精特新/科技型中小企业…)
    tech_domains: List[str] = Field(default_factory=list)  # 技术/产品领域
    keywords: List[str] = Field(default_factory=list)  # 关键词标签
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
