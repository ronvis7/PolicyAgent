from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale
from app.domain.models.enterprise_profile_enrichment import EnterpriseProfileEnrichment

# 字段长度上限(与 ORM 列宽对齐，做输入边界校验)
_MAX_NAME = 255
_MAX_REGION = 64
_MAX_TAG = 64
_MAX_TAGS = 50
_MAX_MAIN_BUSINESS = 5000


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

    @field_validator("qualifications", "tech_domains", "keywords")
    @classmethod
    def _normalize_tags(cls, values: List[str]) -> List[str]:
        return _clean_tags(values)

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
        )


class EnrichEnterpriseProfileRequest(BaseModel):
    """联网增强请求体：以企业名(+可选地区)为线索联网补全档案"""
    company_name: str = Field(min_length=1, max_length=_MAX_NAME)
    province: str = Field(default="", max_length=_MAX_REGION)
    city: str = Field(default="", max_length=_MAX_REGION)
    district: str = Field(default="", max_length=_MAX_REGION)


class EnterpriseProfileEnrichmentResponse(BaseModel):
    """联网增强建议响应：仅作前端回填，不代表已落库"""
    industry: str = ""
    scale: EnterpriseScale = EnterpriseScale.UNSPECIFIED
    main_business: str = ""
    qualifications: List[str] = Field(default_factory=list)
    tech_domains: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    note: str = ""

    @classmethod
    def from_domain(cls, e: EnterpriseProfileEnrichment) -> "EnterpriseProfileEnrichmentResponse":
        """从领域增强模型构建响应"""
        return cls(
            industry=e.industry,
            scale=e.scale,
            main_business=e.main_business,
            qualifications=e.qualifications,
            tech_domains=e.tech_domains,
            keywords=e.keywords,
            sources=e.sources,
            note=e.note,
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
            updated_at=profile.updated_at,
        )
