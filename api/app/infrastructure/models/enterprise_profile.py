from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale


class EnterpriseProfileModel(Base):
    """企业档案ORM模型，每个租户一行，承载组织级结构化信息。

    标量字段直接落列；列表型字段(资质/技术域/关键词)与未来增量字段统一存入 attributes(JSONB)，
    便于在不改表的前提下扩展(如 ①b Agent 增强来源/时间戳)。
    """
    __tablename__ = "enterprise_profiles"

    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )  # 租户id(主键兼外键)
    company_name: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''")
    )  # 企业名称
    province: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''")
    )  # 所在省
    city: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''")
    )  # 所在市
    district: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''")
    )  # 所在区/县
    industry: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''")
    )  # 所属行业
    scale: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'unspecified'")
    )  # 企业规模(枚举值)
    main_business: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )  # 主营业务简介
    attributes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )  # 列表型/增量字段(qualifications/tech_domains/keywords…)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 更新时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )  # 创建时间

    # 经 attributes(JSONB) 承载的结构化标量字段(成立日期/人员/财务/知识产权)，
    # 与领域模型同名；集中维护，避免读写两处各列一遍。None 表示"未填写"，原样存取。
    _SCALAR_ATTRIBUTE_FIELDS = (
        "established_date",
        "total_staff",
        "rd_staff",
        "registered_capital_wan",
        "annual_revenue_wan",
        "rd_investment_wan",
        "invention_patents",
        "other_ip_count",
    )

    @classmethod
    def _attributes_from_domain(cls, profile: EnterpriseProfile) -> dict:
        """将领域模型的列表型与增量标量字段收敛进 attributes(JSONB)"""
        attributes = {
            "qualifications": profile.qualifications,
            "tech_domains": profile.tech_domains,
            "keywords": profile.keywords,
        }
        for name in cls._SCALAR_ATTRIBUTE_FIELDS:
            attributes[name] = getattr(profile, name)
        return attributes

    @classmethod
    def from_domain(cls, profile: EnterpriseProfile) -> "EnterpriseProfileModel":
        """从领域模型创建ORM模型"""
        return cls(
            tenant_id=profile.tenant_id,
            company_name=profile.company_name,
            province=profile.province,
            city=profile.city,
            district=profile.district,
            industry=profile.industry,
            scale=profile.scale.value,
            main_business=profile.main_business,
            attributes=cls._attributes_from_domain(profile),
            updated_at=profile.updated_at,
            created_at=profile.created_at,
        )

    def to_domain(self) -> EnterpriseProfile:
        """将ORM模型转换为领域模型"""
        attributes = self.attributes or {}
        scalars = {
            name: attributes.get(name)
            for name in self._SCALAR_ATTRIBUTE_FIELDS
            if attributes.get(name) is not None
        }
        return EnterpriseProfile(
            tenant_id=self.tenant_id,
            company_name=self.company_name,
            province=self.province,
            city=self.city,
            district=self.district,
            industry=self.industry,
            scale=EnterpriseScale(self.scale),
            main_business=self.main_business,
            qualifications=list(attributes.get("qualifications", [])),
            tech_domains=list(attributes.get("tech_domains", [])),
            keywords=list(attributes.get("keywords", [])),
            updated_at=self.updated_at,
            created_at=self.created_at,
            **scalars,
        )

    def update_from_domain(self, profile: EnterpriseProfile) -> None:
        """从领域模型更新数据"""
        self.company_name = profile.company_name
        self.province = profile.province
        self.city = profile.city
        self.district = profile.district
        self.industry = profile.industry
        self.scale = profile.scale.value
        self.main_business = profile.main_business
        self.attributes = self._attributes_from_domain(profile)
