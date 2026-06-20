"""QualificationTool 单元测试(⑥ 能力③ 材料/流程指引)。

覆盖：清单(可申报/接近)、差距分析(达标/不达标/待确认 + 风险纪律字段)、详情(材料/流程)、
租户隔离、无档案引导、不存在 key。用伪造 UoW 驱动，不依赖数据库；异步方法用 asyncio.run。
"""
import asyncio
from typing import List, Optional

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import (
    ConditionMetric,
    Qualification,
    QualificationCondition,
    QualificationLevel,
)
from app.domain.models.session import Session
from app.domain.services.tools.qualification import QualificationTool

TENANT = "tenant-1"


def _catalog() -> List[Qualification]:
    """两条资质：高企(带结构化硬条件+前置)与一条无结构化条件的通用认证。"""
    return [
        Qualification(
            key="high-tech-enterprise",
            name="高新技术企业认定",
            level=QualificationLevel.NATIONAL,
            region="全国",
            category="科技创新",
            issuer="科技部",
            key_conditions=["注册成立满 1 年以上", "拥有核心自主知识产权", "科技人员占比≥10%"],
            materials=["知识产权证明", "研发费用专项审计报告"],
            timing="每年 6~9 月",
            policy_basis="国科发火〔2016〕32号",
            benefit="所得税减按 15%",
            match_signals=["高新技术", "研发"],
            structured_conditions=[
                QualificationCondition(
                    metric=ConditionMetric.COMPANY_AGE_YEARS, threshold=1,
                    label="注册成立满 1 年以上",
                ),
                QualificationCondition(
                    metric=ConditionMetric.RD_STAFF_RATIO, threshold=10,
                    label="科技人员占比≥10%",
                ),
            ],
            last_reviewed="2026-06-15",
        ),
        Qualification(
            key="iso9001",
            name="ISO9001 质量管理体系认证",
            level=QualificationLevel.GENERAL,
            region="全国",
            match_signals=["质量管理"],
            key_conditions=["建立质量管理体系并运行"],
            materials=["质量手册", "运行记录"],
            last_reviewed="2026-06-15",
        ),
    ]


class FakeSessionRepo:
    def __init__(self, tenant_id: Optional[str]) -> None:
        self._tenant_id = tenant_id

    async def get_by_id(self, session_id: str):
        if self._tenant_id is None:
            return None
        return Session(id=session_id, tenant_id=self._tenant_id)


class FakeProfileRepo:
    def __init__(self, profile: Optional[EnterpriseProfile]) -> None:
        self._profile = profile

    async def get_by_tenant(self, tenant_id: str) -> Optional[EnterpriseProfile]:
        if self._profile is None or self._profile.tenant_id != tenant_id:
            return None
        return self._profile


class FakeUoW:
    def __init__(self, session_repo, profile_repo) -> None:
        self.session = session_repo
        self.enterprise_profile = profile_repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _build_tool(tenant_id: Optional[str], profile: Optional[EnterpriseProfile]) -> QualificationTool:
    uow = FakeUoW(FakeSessionRepo(tenant_id), FakeProfileRepo(profile))
    return QualificationTool(uow_factory=lambda: uow, catalog=_catalog(), session_id="sess-1")


def _profile(**kwargs) -> EnterpriseProfile:
    return EnterpriseProfile(tenant_id=TENANT, **kwargs)


def test_list_returns_candidates_for_tenant_profile():
    """有档案时返回候选清单，行项含 key 与名称。"""
    profile = _profile(tech_domains=["高新技术"], keywords=["研发"])
    tool = _build_tool(TENANT, profile)

    result = asyncio.run(tool.qualification_list())

    assert result.success is True
    assert result.data.kind == "list"
    joined = "\n".join(result.data.lines)
    assert "high-tech-enterprise" in joined
    assert "高新技术企业认定" in joined


def test_list_without_profile_guides_to_fill_profile():
    """无档案时成功返回但引导先完善档案，不报错。"""
    tool = _build_tool(TENANT, None)

    result = asyncio.run(tool.qualification_list())

    assert result.success is True
    assert result.data.lines == []
    assert "档案" in result.data.summary


def test_list_missing_tenant_returns_failure():
    """会话无租户上下文时返回失败。"""
    tool = _build_tool(None, None)

    result = asyncio.run(tool.qualification_list())

    assert result.success is False


def test_gap_reports_met_unmet_unknown_with_risk_fields():
    """差距分析逐条核验：成立年限达标、研发占比不达标，并带免责声明与末次核对日期。"""
    # 成立满 7 年(达标≥1)、研发人员 8/100=8% (不达标 <10%)
    profile = _profile(established_date="2019-01-01", total_staff=100, rd_staff=8)
    tool = _build_tool(TENANT, profile)

    result = asyncio.run(tool.qualification_gap(key="high-tech-enterprise"))

    assert result.success is True
    assert result.data.kind == "gap"
    text = "\n".join(result.data.lines)
    assert "✓" in text and "✗" in text  # 至少一条达标、一条不达标
    assert result.data.disclaimer  # 风险纪律：强制免责声明
    assert result.data.last_reviewed == "2026-06-15"


def test_gap_unknown_when_profile_field_missing():
    """档案缺字段的硬条件判'待确认(?)'，绝不误报不达标。"""
    # 不填人员/成立日期 → 两条硬条件都应为待确认
    profile = _profile()
    tool = _build_tool(TENANT, profile)

    result = asyncio.run(tool.qualification_gap(key="high-tech-enterprise"))

    assert result.success is True
    text = "\n".join(result.data.lines)
    assert "?" in text
    assert "✗" not in text  # 未填不得判不达标


def test_gap_unknown_key_returns_failure():
    """不存在的资质 key 返回失败。"""
    tool = _build_tool(TENANT, _profile())

    result = asyncio.run(tool.qualification_gap(key="nope"))

    assert result.success is False


def test_detail_returns_materials_and_basis():
    """详情返回材料/时间/政策依据/价值，并带风险纪律字段；不依赖租户档案。"""
    tool = _build_tool(TENANT, None)

    result = asyncio.run(tool.qualification_detail(key="high-tech-enterprise"))

    assert result.success is True
    assert result.data.kind == "detail"
    text = "\n".join(result.data.lines)
    assert "知识产权证明" in text  # 材料
    assert "国科发火" in text  # 政策依据
    assert result.data.disclaimer
    assert result.data.last_reviewed == "2026-06-15"


def test_detail_unknown_key_returns_failure():
    """不存在的资质 key 返回失败。"""
    tool = _build_tool(TENANT, None)

    result = asyncio.run(tool.qualification_detail(key="nope"))

    assert result.success is False


def test_apply_plan_aggregates_gap_materials_and_timeline():
    """申报准备方案：聚合条件核验 + 需补齐缺口 + 材料 + 时间线，带风险纪律字段。"""
    # 成立满 7 年(达标)、研发人员 8%(不达标)
    profile = _profile(established_date="2019-01-01", total_staff=100, rd_staff=8)
    tool = _build_tool(TENANT, profile)

    result = asyncio.run(tool.qualification_apply_plan(key="high-tech-enterprise"))

    assert result.success is True
    assert result.data.kind == "plan"
    text = "\n".join(result.data.lines)
    assert "【申报条件核验】" in text
    assert "【需补齐 / 待确认】" in text  # 有不达标项
    assert "【主要申报材料】" in text
    assert "知识产权证明" in text
    assert result.data.disclaimer and result.data.last_reviewed == "2026-06-15"


def test_apply_plan_unknown_key_returns_failure():
    """不存在的资质 key 返回失败。"""
    tool = _build_tool(TENANT, _profile())
    result = asyncio.run(tool.qualification_apply_plan(key="nope"))
    assert result.success is False


def test_apply_plan_missing_tenant_returns_failure():
    """会话无租户上下文时返回失败。"""
    tool = _build_tool(None, None)
    result = asyncio.run(tool.qualification_apply_plan(key="high-tech-enterprise"))
    assert result.success is False
