"""资质目录数据契约测试(⑥)：保证目录可加载且满足匹配/展示所需的结构约束。

目录是人工维护的静态数据，本测试守住"低级数据错误"(重复 key、缺失风险纪律字段、
层级与地区不一致)，不校验业务数值(那些以官方办法为准)。
"""

from app.domain.models.qualification import QualificationLevel
from app.infrastructure.data.qualification_catalog import load_qualification_catalog


def test_catalog_loads_and_is_non_empty() -> None:
    catalog = load_qualification_catalog()
    assert len(catalog) >= 20  # handoff 种子约 24 条


def test_catalog_keys_are_unique() -> None:
    catalog = load_qualification_catalog()
    keys = [q.key for q in catalog]
    assert len(keys) == len(set(keys))


def test_every_qualification_has_required_display_fields() -> None:
    for q in load_qualification_catalog():
        assert q.key and q.name and q.issuer, f"{q.key} 缺少基础字段"
        assert q.policy_basis, f"{q.key} 缺少政策依据"
        assert q.benefit, f"{q.key} 缺少主要价值"


def test_every_qualification_carries_risk_discipline_fields() -> None:
    """风险纪律：每条都须带末次核对日期与免责声明(严禁当权威输出)。"""
    for q in load_qualification_catalog():
        assert q.last_reviewed, f"{q.key} 缺少 last_reviewed"
        assert q.disclaimer, f"{q.key} 缺少 disclaimer"


def test_region_consistent_with_level() -> None:
    """省/市级必须带地区(用于地区门槛)；国家级/通用恒适用。"""
    for q in load_qualification_catalog():
        if q.level in (QualificationLevel.PROVINCIAL, QualificationLevel.MUNICIPAL):
            assert q.region, f"{q.key} 为省/市级却缺少 region"


def test_load_returns_independent_copies() -> None:
    a = load_qualification_catalog()
    a.clear()
    assert len(load_qualification_catalog()) >= 20  # 外部修改不影响共享数据


def test_structured_condition_labels_match_key_conditions() -> None:
    """结构化硬条件的 label 必须逐字命中 key_conditions，否则差距分析会重复展示。"""
    for q in load_qualification_catalog():
        for cond in q.structured_conditions:
            if cond.label:
                assert cond.label in q.key_conditions, (
                    f"{q.key} 的结构化条件 label「{cond.label}」未逐字出现在 key_conditions"
                )


def test_high_tech_enterprise_has_structured_conditions() -> None:
    """高企作为锚点资质应已结构化(成立年限 + 科技人员占比)，保证能力② 端到端可用。"""
    catalog = {q.key: q for q in load_qualification_catalog()}
    hte = catalog["high-tech-enterprise"]
    metrics = {c.metric.value for c in hte.structured_conditions}
    assert "company_age_years" in metrics
    assert "rd_staff_ratio" in metrics
