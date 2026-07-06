"""EnterpriseProfileModel 的 ORM↔领域 转换单测(纯函数，不连库)。

重点验证 A0 新增的结构化字段经 attributes(JSONB) 正确往返，且对老数据(缺这些键)
向后兼容回落默认值——因为这些字段不落独立列、零迁移，转换层是唯一保证。
"""

from datetime import datetime

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale
from app.infrastructure.models.enterprise_profile import EnterpriseProfileModel


def _full_profile() -> EnterpriseProfile:
    return EnterpriseProfile(
        tenant_id="t1",
        company_name="无锡某科技有限公司",
        industry="智能制造",
        scale=EnterpriseScale.SMALL,
        qualifications=["高新技术企业"],
        tech_domains=["工业机器人"],
        keywords=["自动化"],
        established_date="2019-06-01",
        total_staff=120,
        rd_staff=45,
        registered_capital_wan=1000.0,
        annual_revenue_wan=8000.0,
        rd_investment_wan=500.0,
        invention_patents=6,
        other_ip_count=18,
    )


def test_structured_fields_roundtrip_through_jsonb() -> None:
    """from_domain → to_domain 后，结构化字段与列表字段均一致"""
    model = EnterpriseProfileModel.from_domain(_full_profile())

    # 模拟 JSONB 列已落值
    assert model.attributes["established_date"] == "2019-06-01"
    assert model.attributes["total_staff"] == 120
    assert model.attributes["invention_patents"] == 6

    loaded = model.to_domain()
    assert loaded.established_date == "2019-06-01"
    assert loaded.total_staff == 120
    assert loaded.rd_staff == 45
    assert loaded.registered_capital_wan == 1000.0
    assert loaded.annual_revenue_wan == 8000.0
    assert loaded.rd_investment_wan == 500.0
    assert loaded.invention_patents == 6
    assert loaded.other_ip_count == 18
    assert loaded.qualifications == ["高新技术企业"]


def test_legacy_row_without_new_keys_falls_back_to_defaults() -> None:
    """老数据 attributes 缺新键时，to_domain 回落默认(数值 None、日期空串)，不报错"""
    model = EnterpriseProfileModel(
        tenant_id="t1",
        company_name="老档案",
        province="江苏省",
        city="无锡市",
        district="新吴区",
        industry="软件",
        scale="small",
        main_business="",
        attributes={"qualifications": ["高新技术企业"], "tech_domains": [], "keywords": []},
        updated_at=datetime.now(),
        created_at=datetime.now(),
    )

    loaded = model.to_domain()

    assert loaded.established_date == ""
    assert loaded.total_staff is None
    assert loaded.rd_staff is None
    assert loaded.registered_capital_wan is None
    assert loaded.invention_patents is None
    assert loaded.qualifications == ["高新技术企业"]
    assert loaded.contest_regions == []  # 老数据缺键回落空列表(不限地区)


def test_contest_regions_roundtrip_through_jsonb() -> None:
    """参赛关注地区经 attributes(JSONB) 正确往返(零迁移新增列表字段)。"""
    profile = EnterpriseProfile(tenant_id="t1", contest_regions=["江苏省", "重庆市"])
    model = EnterpriseProfileModel.from_domain(profile)

    assert model.attributes["contest_regions"] == ["江苏省", "重庆市"]
    assert model.to_domain().contest_regions == ["江苏省", "重庆市"]


def test_unset_numeric_fields_persist_as_none() -> None:
    """未填写的数值字段以 None 落入 attributes，区别于填了0"""
    model = EnterpriseProfileModel.from_domain(EnterpriseProfile(tenant_id="t1", total_staff=0))

    assert model.attributes["total_staff"] == 0  # 显式填0保留
    assert model.attributes["rd_staff"] is None  # 未填写为 None

    loaded = model.to_domain()
    assert loaded.total_staff == 0
    assert loaded.rd_staff is None
