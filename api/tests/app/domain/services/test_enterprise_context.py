"""企业档案上下文渲染纯函数单测。

覆盖：空档案(None / 仅缺企业名)走引导块、已填档案渲染关键字段、
未填写的经营研发指标不渲染(区分未填写与 0)。无 IO。
"""

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale
from app.domain.services.enterprise_context import render_enterprise_context


def test_none_profile_returns_empty_guidance_block():
    """档案为 None：返回引导用户去档案页填写的提示块，不暴露字段。"""
    ctx = render_enterprise_context(None)
    assert "尚未填写企业档案" in ctx
    assert "企业档案" in ctx
    # 引导而非反问
    assert "不要在对话中逐项追问" in ctx


def test_profile_without_company_name_treated_as_empty():
    """仅有默认地区、无企业名：仍视为空档案走引导块。"""
    ctx = render_enterprise_context(EnterpriseProfile(tenant_id="t1"))
    assert "尚未填写企业档案" in ctx


def test_filled_profile_renders_key_fields():
    """已填档案：关键字段进入上下文块，并声明'无需向用户索取'。"""
    profile = EnterpriseProfile(
        tenant_id="t1",
        company_name="无锡某智能科技有限公司",
        province="江苏省",
        city="无锡市",
        district="新吴区",
        industry="智能制造",
        scale=EnterpriseScale.SMALL,
        main_business="工业机器人研发与系统集成",
        qualifications=["高新技术企业"],
        tech_domains=["工业机器人"],
        keywords=["自动化"],
        established_date="2018-05-01",
        total_staff=120,
        rd_staff=35,
    )
    ctx = render_enterprise_context(profile)

    assert "无锡某智能科技有限公司" in ctx
    assert "智能制造" in ctx
    assert "小型企业" in ctx
    assert "工业机器人研发与系统集成" in ctx
    assert "高新技术企业" in ctx
    assert "员工总数 120 人" in ctx
    assert "研发人员 35 人" in ctx
    # 行为约束：直接用档案分析、无需索取
    assert "无需再向用户索取" in ctx


def test_unfilled_metrics_are_omitted():
    """未填写的经营研发指标(None)不渲染，避免与'填了0'混淆。"""
    profile = EnterpriseProfile(
        tenant_id="t1",
        company_name="某企业",
        annual_revenue_wan=0,  # 明确填了 0：应渲染
        # rd_investment_wan 未填(None)：不渲染
    )
    ctx = render_enterprise_context(profile)
    assert "上年度营收 0" in ctx
    assert "研发投入" not in ctx
