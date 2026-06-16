import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale

# 字段长度上限(与 ORM 列宽对齐，做输入边界校验)
_MAX_NAME = 255
_MAX_REGION = 64
_MAX_TAG = 64
_MAX_TAGS = 50
_MAX_MAIN_BUSINESS = 5000

# 成立日期接受空串或 YYYY / YYYY-MM / YYYY-MM-DD(精度由企业自定，宽松校验防脏数据)
_DATE_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _clean_tags(values: List[str]) -> List[str]:
    """去空白、丢空值、按序去重，并限制单标签长度与数量"""
    seen: set[str] = set()
    cleaned: List[str] = []
    for raw in values:
        tag = (raw or "").strip()[:_MAX_TAG]
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    return cleaned[:_MAX_TAGS]


class UpdateEnterpriseProfileRequest(BaseModel):
    """更新企业档案请求体"""
    company_name: str = Field(default="", max_length=_MAX_NAME)
    province: str = Field(default="", max_length=_MAX_REGION)
    city: str = Field(default="", max_length=_MAX_REGION)
    district: str = Field(default="", max_length=_MAX_REGION)
    industry: str = Field(default="", max_length=_MAX_NAME)
    scale: EnterpriseScale = EnterpriseScale.UNSPECIFIED
    main_business: str = Field(default="", max_length=_MAX_MAIN_BUSINESS)
    qualifications: List[str] = Field(default_factory=list)
    tech_domains: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    # ---- 结构化资质条件字段(均可空；数值非负)----
    established_date: str = Field(default="", max_length=10)  # 成立/注册日期
    total_staff: Optional[int] = Field(default=None, ge=0)  # 员工总数
    rd_staff: Optional[int] = Field(default=None, ge=0)  # 研发人员数
    registered_capital_wan: Optional[float] = Field(default=None, ge=0)  # 注册资本(万元)
    annual_revenue_wan: Optional[float] = Field(default=None, ge=0)  # 上年度营收(万元)
    rd_investment_wan: Optional[float] = Field(default=None, ge=0)  # 上年度研发投入(万元)
    invention_patents: Optional[int] = Field(default=None, ge=0)  # 发明专利数
    other_ip_count: Optional[int] = Field(default=None, ge=0)  # 其他知识产权数

    @field_validator("qualifications", "tech_domains", "keywords")
    @classmethod
    def _normalize_tags(cls, values: List[str]) -> List[str]:
        return _clean_tags(values)

    @field_validator("established_date")
    @classmethod
    def _validate_date(cls, value: str) -> str:
        value = (value or "").strip()
        if value and not _DATE_PATTERN.match(value):
            raise ValueError("established_date 需为空或 YYYY / YYYY-MM / YYYY-MM-DD 格式")
        return value

    def to_domain(self, tenant_id: str) -> EnterpriseProfile:
        """转换为领域模型(时间戳由服务层统一处理)"""
        return EnterpriseProfile(
            tenant_id=tenant_id,
            company_name=self.company_name.strip(),
            province=self.province.strip(),
            city=self.city.strip(),
            district=self.district.strip(),
            industry=self.industry.strip(),
            scale=self.scale,
            main_business=self.main_business.strip(),
            qualifications=self.qualifications,
            tech_domains=self.tech_domains,
            keywords=self.keywords,
            established_date=self.established_date,
            total_staff=self.total_staff,
            rd_staff=self.rd_staff,
            registered_capital_wan=self.registered_capital_wan,
            annual_revenue_wan=self.annual_revenue_wan,
            rd_investment_wan=self.rd_investment_wan,
            invention_patents=self.invention_patents,
            other_ip_count=self.other_ip_count,
        )


class EnterpriseProfileResponse(BaseModel):
    """企业档案响应结构"""
    company_name: str = ""
    province: str = ""
    city: str = ""
    district: str = ""
    industry: str = ""
    scale: EnterpriseScale = EnterpriseScale.UNSPECIFIED
    main_business: str = ""
    qualifications: List[str] = Field(default_factory=list)
    tech_domains: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    established_date: str = ""
    total_staff: Optional[int] = None
    rd_staff: Optional[int] = None
    registered_capital_wan: Optional[float] = None
    annual_revenue_wan: Optional[float] = None
    rd_investment_wan: Optional[float] = None
    invention_patents: Optional[int] = None
    other_ip_count: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_domain(cls, profile: EnterpriseProfile) -> "EnterpriseProfileResponse":
        """从领域模型构建响应"""
        return cls(
            company_name=profile.company_name,
            province=profile.province,
            city=profile.city,
            district=profile.district,
            industry=profile.industry,
            scale=profile.scale,
            main_business=profile.main_business,
            qualifications=profile.qualifications,
            tech_domains=profile.tech_domains,
            keywords=profile.keywords,
            established_date=profile.established_date,
            total_staff=profile.total_staff,
            rd_staff=profile.rd_staff,
            registered_capital_wan=profile.registered_capital_wan,
            annual_revenue_wan=profile.annual_revenue_wan,
            rd_investment_wan=profile.rd_investment_wan,
            invention_patents=profile.invention_patents,
            other_ip_count=profile.other_ip_count,
            updated_at=profile.updated_at,
        )
