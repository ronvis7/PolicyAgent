"""BriefingService 单元测试（主动情报 Agent 编排层）。

覆盖：无 LLM 走兜底并持久化、LLM 解析成功用 LLM 结果、LLM 异常回退兜底、
get_latest 读取、regenerate_all 遍历已建档租户。用内存级 UoW + 桩 report/llm。
"""
import asyncio
from typing import Optional

from app.application.services.briefing_service import BriefingService
from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem, FeedItemType
from app.domain.models.intel_briefing import IntelBriefing
from app.domain.models.report import ReportData
from ._fakes import make_uow_factory

TENANT = "tenant-1"


def _report(tenant_id: str = TENANT) -> ReportData:
    return ReportData(
        tenant_id=tenant_id,
        profile=EnterpriseProfile(tenant_id=tenant_id, company_name="某科技", industry="智能制造"),
        matched_policies=[FeedItem(
            tenant_id=tenant_id, type=FeedItemType.POLICY, policy_id="p1",
            title="研发补贴政策", reasons=["命中：研发"],
        )],
    )


class FakeReportService:
    def __init__(self, data: ReportData) -> None:
        self._data = data

    async def build_brief(self, tenant_id: str) -> ReportData:
        return self._data


class FakeLLM:
    def __init__(self, content: Optional[str], raise_exc: bool = False) -> None:
        self._content = content
        self._raise = raise_exc

    async def invoke(self, messages, tools=None, response_format=None, tool_choice=None):
        if self._raise:
            raise RuntimeError("llm down")
        return {"role": "assistant", "content": self._content}


def test_generate_without_llm_uses_fallback_and_persists():
    """无 LLM：走确定性兜底并落库。"""
    store = {}
    service = BriefingService(
        uow_factory=make_uow_factory(intel_briefings=store),
        report_service=FakeReportService(_report()),
        llm=None,
    )

    briefing = asyncio.run(service.generate(TENANT))

    assert briefing.generated_by == "fallback"
    assert any(i.title == "研发补贴政策" for i in briefing.items)
    assert TENANT in store  # 已持久化


def test_generate_with_llm_uses_parsed_result():
    """LLM 返回合法 JSON：采用 LLM 结果。"""
    content = '{"headline":"本期1个机会","items":[{"title":"研发补贴政策","category":"政策机会","urgency":"normal"}]}'
    service = BriefingService(
        uow_factory=make_uow_factory(),
        report_service=FakeReportService(_report()),
        llm=FakeLLM(content),
    )

    briefing = asyncio.run(service.generate(TENANT))

    assert briefing.generated_by == "llm"
    assert briefing.headline == "本期1个机会"


def test_generate_llm_exception_falls_back():
    """LLM 抛错：回退兜底，不抛出。"""
    service = BriefingService(
        uow_factory=make_uow_factory(),
        report_service=FakeReportService(_report()),
        llm=FakeLLM(None, raise_exc=True),
    )

    briefing = asyncio.run(service.generate(TENANT))

    assert briefing.generated_by == "fallback"


def test_get_latest_returns_persisted():
    """get_latest 读取已存简报。"""
    store = {TENANT: IntelBriefing(tenant_id=TENANT, headline="旧简报")}
    service = BriefingService(
        uow_factory=make_uow_factory(intel_briefings=store),
        report_service=FakeReportService(_report()),
    )

    latest = asyncio.run(service.get_latest(TENANT))

    assert latest is not None
    assert latest.headline == "旧简报"


def test_regenerate_all_iterates_profiled_tenants():
    """批量重算：遍历所有已建档租户。"""
    profiles = {
        "t1": EnterpriseProfile(tenant_id="t1", company_name="A"),
        "t2": EnterpriseProfile(tenant_id="t2", company_name="B"),
    }
    briefings = {}
    service = BriefingService(
        uow_factory=make_uow_factory(enterprise_profiles=profiles, intel_briefings=briefings),
        report_service=FakeReportService(_report()),
    )

    count = asyncio.run(service.regenerate_all())

    assert count == 2
    assert set(briefings.keys()) == {"t1", "t2"}
