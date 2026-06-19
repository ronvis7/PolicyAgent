"""PDF 渲染器冒烟测试：产出合法非空 PDF 字节，中文/各区块不抛异常。"""

from datetime import date

from app.domain.models.enterprise_profile import EnterpriseProfile, EnterpriseScale
from app.domain.models.feed_item import FeedItem, FeedItemType
from app.domain.models.qualification import (
    ConditionCheck,
    ConditionMetric,
    ConditionOperator,
    ConditionStatus,
    Qualification,
    QualificationGapReport,
    QualificationLevel,
)
from app.domain.models.report import ReportData
from app.infrastructure.report.pdf_renderer import render_brief


def _sample_report() -> ReportData:
    profile = EnterpriseProfile(
        tenant_id="t1", company_name="无锡示范科技有限公司", industry="集成电路",
        scale=EnterpriseScale.SMALL, main_business="芯片设计",
        qualifications=["科技型中小企业"], tech_domains=["集成电路", "EDA"],
    )
    policy = FeedItem(
        tenant_id="t1", type=FeedItemType.POLICY, policy_id="p1",
        title="新吴区集成电路产业扶持政策", issuer="新吴区科技局", score=0.87,
        apply_deadline=date(2026, 7, 31), deadline_status="extracted",
        reasons=["命中关键词：集成电路"],
    )
    qual = Qualification(
        key="high-tech-enterprise", name="高新技术企业", level=QualificationLevel.NATIONAL,
        last_reviewed="2026-06-15",
    )
    gap = QualificationGapReport(
        qualification=qual,
        checks=[
            ConditionCheck(
                metric=ConditionMetric.COMPANY_AGE_YEARS, op=ConditionOperator.GTE,
                threshold=1, actual=7, status=ConditionStatus.MET, label="成立满1年", detail="成立7年",
            ),
            ConditionCheck(
                metric=ConditionMetric.RD_STAFF_RATIO, op=ConditionOperator.GTE,
                threshold=10, actual=8, status=ConditionStatus.UNMET,
                label="研发人员占比≥10%", detail="研发人员占比 8% < 10%",
            ),
        ],
        manual_review=["近三年研发费用占比达标"],
        met_count=1, unmet_count=1, unknown_count=0, summary="差研发人员占比一项",
    )
    return ReportData(
        tenant_id="t1", profile=profile,
        matched_policies=[policy], qualification_gaps=[gap], expiring=[policy],
    )


def test_render_brief_produces_pdf_bytes():
    pdf = render_brief(_sample_report())
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000  # 非空、含内容


def test_render_brief_empty_profile_does_not_raise():
    data = ReportData(tenant_id="t1", profile=EnterpriseProfile(tenant_id="t1"))
    pdf = render_brief(data)
    assert pdf.startswith(b"%PDF")


def test_render_brief_escapes_xml_special_chars():
    """政策标题/业务含 & < > 不应让 reportlab 解析 mini-HTML 时抛异常。"""
    profile = EnterpriseProfile(
        tenant_id="t1", company_name="A & B <科技>", main_business="研发 <芯片> & 软件",
    )
    policy = FeedItem(
        tenant_id="t1", type=FeedItemType.POLICY, policy_id="p1",
        title="关于 <制造业> & 数字化 的若干意见", issuer="发改委 & 工信部", score=0.5,
    )
    data = ReportData(tenant_id="t1", profile=profile, matched_policies=[policy])
    pdf = render_brief(data)
    assert pdf.startswith(b"%PDF")
