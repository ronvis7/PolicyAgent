"""主动情报简报组装器纯函数单测。

覆盖：事实压缩、LLM JSON 解析(成功/脏数据回 None)、urgency 安全转换、
确定性兜底(临期→high、按临期/政策/资质顺序、上限 6)。无 IO。
"""
from datetime import date

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType
from app.domain.models.intel_briefing import BriefingUrgency
from app.domain.models.qualification import (
    Qualification,
    QualificationGapReport,
    QualificationLevel,
)
from app.domain.models.report import ReportData
from app.domain.services.briefing_composer import (
    build_facts,
    fallback_briefing,
    parse_briefing,
)

TODAY = date(2026, 6, 20)


def _report(**kwargs) -> ReportData:
    profile = kwargs.pop("profile", EnterpriseProfile(
        tenant_id="t1", company_name="某智能科技", industry="智能制造",
    ))
    return ReportData(
        tenant_id="t1",
        profile=profile,
        matched_policies=kwargs.get("matched_policies", []),
        qualification_gaps=kwargs.get("qualification_gaps", []),
        expiring=kwargs.get("expiring", []),
    )


def _policy(title: str, reasons=None) -> FeedItem:
    return FeedItem(
        tenant_id="t1", type=FeedItemType.POLICY, policy_id=title,
        title=title, reasons=reasons or [],
    )


def _expiring(title: str, deadline: date) -> FeedItem:
    return FeedItem(
        tenant_id="t1", type=FeedItemType.POLICY, policy_id=title, title=title,
        apply_deadline=deadline, deadline_status="extracted",
    )


def _gap(name: str, summary: str) -> QualificationGapReport:
    qual = Qualification(key=name, name=name, level=QualificationLevel.GENERAL, region="全国")
    return QualificationGapReport(qualification=qual, summary=summary)


def test_build_facts_compacts_and_caps():
    """事实压缩：保留标题/理由，理由截断到 3 条。"""
    policies = [_policy(f"政策{i}", reasons=["a", "b", "c", "d"]) for i in range(10)]
    facts = build_facts(_report(matched_policies=policies), TODAY)

    assert facts["company"] == "某智能科技"
    assert len(facts["matched_policies"]) == 8  # _MAX_POLICIES
    assert facts["matched_policies"][0]["reasons"] == ["a", "b", "c"]


def test_parse_briefing_success():
    """解析合法 JSON：得到带项的简报，generated_by=llm。"""
    content = (
        '{"headline":"本期有 2 个机会","items":['
        '{"title":"高企认定","category":"资质机会","reason":"接近达标","action":"补齐占比","urgency":"high"},'
        '{"title":"研发补贴","category":"政策机会","reason":"命中研发","action":"看原文","urgency":"normal"}'
        ']}'
    )
    briefing = parse_briefing("t1", content)

    assert briefing is not None
    assert briefing.generated_by == "llm"
    assert briefing.headline == "本期有 2 个机会"
    assert [i.title for i in briefing.items] == ["高企认定", "研发补贴"]
    assert briefing.items[0].urgency == BriefingUrgency.HIGH


def test_parse_briefing_tolerates_code_fence():
    """容忍 ```json 包裹。"""
    content = '```json\n{"headline":"h","items":[{"title":"x"}]}\n```'
    briefing = parse_briefing("t1", content)
    assert briefing is not None
    assert briefing.items[0].title == "x"
    assert briefing.items[0].urgency == BriefingUrgency.NORMAL  # 缺省安全转换


def test_parse_briefing_garbage_returns_none():
    """脏数据/非 JSON：返回 None 交由兜底。"""
    assert parse_briefing("t1", "这不是JSON") is None
    assert parse_briefing("t1", '{"headline":"h"}') is None  # 缺 items


def test_fallback_prioritizes_expiring_as_high():
    """兜底：临期项排最前且 ≤7 天判 high。"""
    report = _report(
        matched_policies=[_policy("研发补贴", reasons=["命中：研发"])],
        qualification_gaps=[_gap("高企", "成立达标、占比待确认")],
        expiring=[_expiring("专精特新申报", date(2026, 6, 25))],  # 5 天后
    )
    briefing = fallback_briefing("t1", report, TODAY)

    assert briefing.generated_by == "fallback"
    assert briefing.items[0].title == "专精特新申报"
    assert briefing.items[0].category == "临期申报"
    assert briefing.items[0].urgency == BriefingUrgency.HIGH
    titles = [i.title for i in briefing.items]
    assert "研发补贴" in titles and "高企" in titles


def test_fallback_caps_at_six_items():
    """兜底上限 6 条。"""
    report = _report(matched_policies=[_policy(f"政策{i}") for i in range(10)])
    briefing = fallback_briefing("t1", report, TODAY)
    assert len(briefing.items) == 6
