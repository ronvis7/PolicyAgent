"""EnterpriseProfileService 离线单元测试：按租户读写结构化企业档案。

异步方法用 asyncio.run 驱动，避免依赖 pytest-asyncio 插件(与本仓库其他测试一致)。
"""

import asyncio

from app.application.services.enterprise_profile_service import EnterpriseProfileService
from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale

from ._fakes import make_uow_factory

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"


def _service() -> EnterpriseProfileService:
    return EnterpriseProfileService(uow_factory=make_uow_factory())


def test_get_returns_default_region_when_unset() -> None:
    """从未填写过时返回带默认地区(无锡新吴区)的空档案"""
    service = _service()

    profile = asyncio.run(service.get_profile(TENANT_A))

    assert profile.tenant_id == TENANT_A
    assert profile.company_name == ""
    assert (profile.province, profile.city, profile.district) == ("江苏省", "无锡市", "新吴区")
    assert profile.scale is EnterpriseScale.UNSPECIFIED


def test_update_then_get_roundtrips_all_fields() -> None:
    """更新后再读取，标量与列表字段均正确往返"""
    service = _service()
    new_profile = EnterpriseProfile(
        company_name="无锡某智能制造有限公司",
        province="江苏省",
        city="无锡市",
        district="新吴区",
        industry="智能制造",
        scale=EnterpriseScale.SMALL,
        main_business="工业机器人研发与集成",
        qualifications=["高新技术企业", "科技型中小企业"],
        tech_domains=["工业机器人", "机器视觉"],
        keywords=["智能制造", "自动化"],
    )

    asyncio.run(service.update_profile(TENANT_A, new_profile))
    loaded = asyncio.run(service.get_profile(TENANT_A))

    assert loaded.company_name == "无锡某智能制造有限公司"
    assert loaded.industry == "智能制造"
    assert loaded.scale is EnterpriseScale.SMALL
    assert loaded.qualifications == ["高新技术企业", "科技型中小企业"]
    assert loaded.tech_domains == ["工业机器人", "机器视觉"]
    assert loaded.keywords == ["智能制造", "自动化"]


def test_update_then_get_roundtrips_structured_fields() -> None:
    """新增的结构化资质条件字段(成立日期/人员/财务/知识产权)经 JSONB 正确往返"""
    service = _service()
    new_profile = EnterpriseProfile(
        company_name="无锡某科技有限公司",
        established_date="2019-06-01",
        total_staff=120,
        rd_staff=45,
        registered_capital_wan=1000.0,
        annual_revenue_wan=8000.0,
        rd_investment_wan=500.0,
        invention_patents=6,
        other_ip_count=18,
    )

    asyncio.run(service.update_profile(TENANT_A, new_profile))
    loaded = asyncio.run(service.get_profile(TENANT_A))

    assert loaded.established_date == "2019-06-01"
    assert loaded.total_staff == 120
    assert loaded.rd_staff == 45
    assert loaded.registered_capital_wan == 1000.0
    assert loaded.annual_revenue_wan == 8000.0
    assert loaded.rd_investment_wan == 500.0
    assert loaded.invention_patents == 6
    assert loaded.other_ip_count == 18


def test_structured_fields_default_to_none_when_unset() -> None:
    """未填写的结构化字段保持 None(与填了0区分)，成立日期为空串"""
    service = _service()
    asyncio.run(service.update_profile(TENANT_A, EnterpriseProfile(company_name="只填了名字")))

    loaded = asyncio.run(service.get_profile(TENANT_A))

    assert loaded.established_date == ""
    assert loaded.total_staff is None
    assert loaded.rd_staff is None
    assert loaded.invention_patents is None


def test_update_is_upsert_and_overwrites() -> None:
    """二次更新整体覆盖既有档案"""
    service = _service()
    asyncio.run(service.update_profile(
        TENANT_A, EnterpriseProfile(company_name="旧名", industry="软件", keywords=["a", "b"])
    ))

    asyncio.run(service.update_profile(
        TENANT_A, EnterpriseProfile(company_name="新名", industry="制造", keywords=["c"])
    ))
    loaded = asyncio.run(service.get_profile(TENANT_A))

    assert loaded.company_name == "新名"
    assert loaded.industry == "制造"
    assert loaded.keywords == ["c"]


def test_update_forces_tenant_id_from_context() -> None:
    """即使请求体携带其他 tenant_id，也以上下文租户为准，防止越权写入"""
    service = _service()

    saved = asyncio.run(service.update_profile(
        TENANT_A, EnterpriseProfile(tenant_id="forged-tenant", company_name="X")
    ))

    assert saved.tenant_id == TENANT_A
    assert asyncio.run(service.get_profile("forged-tenant")).company_name == ""


def test_tenants_are_isolated() -> None:
    """一个组织的档案不影响另一个组织"""
    service = _service()

    asyncio.run(service.update_profile(TENANT_A, EnterpriseProfile(company_name="A公司")))
    profile_b = asyncio.run(service.get_profile(TENANT_B))

    assert profile_b.company_name == ""


def test_update_preserves_created_at() -> None:
    """二次更新保留首次创建时间，仅刷新 updated_at"""
    service = _service()
    first = asyncio.run(service.update_profile(TENANT_A, EnterpriseProfile(company_name="A")))

    second = asyncio.run(service.update_profile(TENANT_A, EnterpriseProfile(company_name="B")))

    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at
