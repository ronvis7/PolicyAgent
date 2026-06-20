"""主动情报简报服务（主动情报 Agent 的编排层）。

把"聚合机会(复用 ReportService) → LLM 归纳带理由的优先级简报 → 持久化最新一份"串起来，
并提供按租户读取最新简报、以及供定时任务为所有已建档租户批量重算的入口。

best-effort 纪律：无 LLM / 调用失败 / 解析失败 一律回退确定性兜底简报(briefing_composer.fallback)，
保证"主动情报"始终有产出；单租户失败不影响批量其余租户。
"""

import logging
from datetime import date
from typing import Callable, List, Optional, Protocol

from app.domain.models.intel_briefing import IntelBriefing
from app.domain.models.report import ReportData
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.briefing_composer import (
    build_facts,
    build_messages,
    fallback_briefing,
    parse_briefing,
)

logger = logging.getLogger(__name__)


class _BriefReader(Protocol):
    async def build_brief(self, tenant_id: str) -> ReportData: ...


class _LLM(Protocol):
    async def invoke(self, messages, tools=None, response_format=None, tool_choice=None): ...


class BriefingService:
    """主动情报简报：生成/读取/批量重算（每租户最新一份）。"""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        report_service: _BriefReader,
        llm: Optional[_LLM] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._report_service = report_service
        self._llm = llm

    async def generate(self, tenant_id: str) -> IntelBriefing:
        """为某租户生成并持久化一份最新情报简报（LLM 优先，失败兜底）。"""
        data = await self._report_service.build_brief(tenant_id)
        briefing = await self._compose(tenant_id, data)
        async with self._uow_factory() as uow:
            await uow.intel_briefing.save(briefing)
        logger.info(
            "情报简报已生成 tenant=%s by=%s items=%d",
            tenant_id, briefing.generated_by, len(briefing.items),
        )
        return briefing

    async def _compose(self, tenant_id: str, data: ReportData) -> IntelBriefing:
        """LLM 归纳优先；无 LLM/失败/解析失败回退确定性兜底。"""
        today = date.today()
        if self._llm is not None:
            try:
                facts = build_facts(data, today)
                message = await self._llm.invoke(build_messages(facts))
                content = (message or {}).get("content") or ""
                parsed = parse_briefing(tenant_id, content)
                if parsed is not None:
                    return parsed
            except Exception as e:  # noqa: BLE001 — 简报为增强，失败不应阻断，回退兜底
                logger.warning("情报简报 LLM 生成失败，回退兜底 tenant=%s: %s", tenant_id, e)
        return fallback_briefing(tenant_id, data, today)

    async def get_latest(self, tenant_id: str) -> Optional[IntelBriefing]:
        """读取某租户最新一份情报简报（从未生成则 None）。"""
        async with self._uow_factory() as uow:
            return await uow.intel_briefing.get_by_tenant(tenant_id)

    async def regenerate_all(self) -> int:
        """为所有已建档租户批量重算简报（供定时任务调用），返回成功条数。"""
        async with self._uow_factory() as uow:
            tenant_ids: List[str] = await uow.enterprise_profile.list_tenant_ids()

        count = 0
        for tenant_id in tenant_ids:
            try:
                await self.generate(tenant_id)
                count += 1
            except Exception as e:  # noqa: BLE001 — 单租户失败不影响其余
                logger.warning("情报简报批量重算失败 tenant=%s: %s", tenant_id, e)
        logger.info("情报简报批量重算完成：%d/%d 成功", count, len(tenant_ids))
        return count
