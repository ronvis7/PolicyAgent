from datetime import datetime
from enum import Enum
from typing import List, Optional

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
    # 参赛关注地区(赛事机会按此过滤；比赛可异地参加，与所在地解耦)。空=不限。
    # 取值为已接入赛事来源的 region 串(如"江苏省"/"重庆市")，层级前缀匹配见 contest_region_matches。
    contest_regions: List[str] = Field(default_factory=list)
    # ---- 结构化资质条件字段(手动填写，供 ⑥ 差距分析)----
    # 统一用 Optional[...]=None 表达"未填写"，与"填了0"区分(差距分析里未知≠不达标)。
    established_date: str = ""  # 成立/注册日期(YYYY-MM-DD)，用于"成立满N年"类硬条件
    total_staff: Optional[int] = None  # 员工总数
    rd_staff: Optional[int] = None  # 研发人员数
    registered_capital_wan: Optional[float] = None  # 注册资本(万元)
    annual_revenue_wan: Optional[float] = None  # 上年度营收(万元)
    rd_investment_wan: Optional[float] = None  # 上年度研发投入(万元)
    invention_patents: Optional[int] = None  # 发明专利数(Ⅰ类知识产权)
    other_ip_count: Optional[int] = None  # 其他知识产权数(实用新型/软著/外观等，Ⅱ类)
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
