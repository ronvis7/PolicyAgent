"""资质申报指引工具(主线⑥ 能力③：材料/流程指引)。

把静态资质目录与"企业档案 × 资质"差距分析暴露给 Agent，使其在聊天链路里能：
1. 按当前租户档案列出可申报/接近候选(qualification_list)，定位用户提到的资质；
2. 取某资质的条件差距分析(qualification_gap)——达标/不达标/待确认 + 需人工确认的软条件，
   作为生成"材料清单 + 申报流程指引"的事实底座；
3. 取某资质的材料/时间/政策依据/价值(qualification_detail)。

设计要点：
- 工具内核全部走 **domain 纯函数**(match_qualifications / analyze_gap) + uow 读档案，
  不依赖 application/infrastructure，保持分层；目录(catalog)由构造链从外部注入。
- 租户范围由会话懒加载得到(同 KnowledgeBaseTool)，确保多租户隔离。
- 返回的 gap/detail 强制带 `disclaimer` + `last_reviewed`(风险纪律：门槛为结构性概要，
  严禁当权威输出)；并在工具说明里要求 Agent 结合 knowledge_base_search 取政策原文交叉核对，
  把"待确认/需人工确认"的软条件交由原文深化(混合引擎的"软"半边)。
"""

import logging
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import ConditionStatus, Qualification
from app.domain.models.tool_result import ToolResult
from app.domain.repositories.uow import IUnitOfWork
from app.domain.services.qualification_gap import analyze_gap
from app.domain.services.qualification_matcher import match_qualifications
from .base import BaseTool, tool

logger = logging.getLogger(__name__)

# 差距分析逐条状态对应的人读图标
_STATUS_ICON = {
    ConditionStatus.MET: "✓",
    ConditionStatus.UNMET: "✗",
    ConditionStatus.UNKNOWN: "?",
}


class QualificationToolData(BaseModel):
    """资质指引工具的统一返回体(同时供 LLM 观察与前端卡片渲染)。

    `lines` 为已格式化的人读要点；`kind` 区分 list/gap/detail 供前端按需呈现。
    """
    kind: str  # list | gap | detail
    title: str  # 资质名称或"可申报资质"
    summary: str = ""  # 一句话总览
    lines: List[str] = Field(default_factory=list)  # 人读要点(逐条)
    disclaimer: str = ""  # 免责声明(gap/detail 强制)
    last_reviewed: str = ""  # 末次核对日期(gap/detail 强制)


class QualificationTool(BaseTool):
    """资质申报指引工具集(⑥ 能力③)。"""
    name: str = "qualification"

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        catalog: List[Qualification],
        session_id: str,
    ) -> None:
        """构造函数，注入资质目录与会话上下文。"""
        super().__init__()
        self._uow_factory = uow_factory
        self._catalog = list(catalog)
        self._by_key = {q.key: q for q in self._catalog}
        self._session_id = session_id
        # 会话租户懒加载缓存(隔离边界)
        self._tenant_id: Optional[str] = None
        self._scope_loaded = False

    async def _get_tenant_id(self) -> Optional[str]:
        """懒加载并返回当前会话所属租户id，作为档案读取的隔离边界。"""
        if not self._scope_loaded:
            async with self._uow_factory() as uow:
                session = await uow.session.get_by_id(self._session_id)
            self._tenant_id = session.tenant_id if session else None
            self._scope_loaded = True
        return self._tenant_id

    async def _load_profile(self, tenant_id: str) -> Optional[EnterpriseProfile]:
        """读取当前租户企业档案(差距分析/匹配的输入)。"""
        async with self._uow_factory() as uow:
            return await uow.enterprise_profile.get_by_tenant(tenant_id)

    @tool(
        name="qualification_list",
        description=(
            "列出当前企业(租户)按其档案匹配到的可申报/接近可申报资质清单(资质=政策定义的、"
            "相对稳定的申报机会，如高新技术企业、专精特新等)。当用户问'我能申报哪些资质/"
            "我适合什么资质/有哪些扶持认定'时**直接调用本工具**。"
            "本工具会自动读取当前登录企业的档案，**无需用户提供任何企业信息，切勿反问用户企业名称/行业/规模等**。"
            "返回每条资质的 key、名称与是否可申报，key 可用于后续 qualification_gap / qualification_detail 进一步分析。"
        ),
        parameters={},
        required=[],
    )
    async def qualification_list(self) -> ToolResult[QualificationToolData]:
        """按当前租户档案返回可申报资质候选。"""
        tenant_id = await self._get_tenant_id()
        if not tenant_id:
            return ToolResult(success=False, message="当前会话缺少租户上下文，无法匹配资质")

        profile = await self._load_profile(tenant_id)
        if profile is None:
            return ToolResult(
                success=True,
                message="当前企业尚未填写档案",
                data=QualificationToolData(
                    kind="list", title="可申报资质",
                    summary=(
                        "系统未读到当前企业的档案。请引导用户前往左侧「企业档案」页面一键完善"
                        "（一次填写、后续自动使用），不要在对话中逐项追问企业信息。"
                    ),
                ),
            )

        matches = match_qualifications(profile, self._catalog)
        if not matches:
            return ToolResult(
                success=True,
                message="未匹配到适用资质",
                data=QualificationToolData(
                    kind="list", title="可申报资质",
                    summary="按当前档案未匹配到适用资质，可完善行业/技术域/关键词后重试。",
                ),
            )

        lines: List[str] = []
        for m in matches:
            tag = "可申报" if m.eligible else "接近可申报"
            line = f"[{m.qualification.key}] {m.qualification.name}（{tag}）"
            if m.missing_prerequisites:
                line += f"；缺前置：{'、'.join(m.missing_prerequisites)}"
            lines.append(line)

        eligible = sum(1 for m in matches if m.eligible)
        return ToolResult(
            success=True,
            message=f"匹配到 {len(matches)} 项资质候选",
            data=QualificationToolData(
                kind="list", title="可申报资质",
                summary=f"共 {len(matches)} 项候选，其中可申报 {eligible} 项。",
                lines=lines,
            ),
        )

    @tool(
        name="qualification_gap",
        description=(
            "对指定资质(由 key 指定，可先用 qualification_list 取得)做'企业档案 × 申报条件'"
            "差距分析：逐条给出 达标(✓)/不达标(✗)/待确认(?，档案未填)，并列出缺失的前置资质与"
            "'需结合材料/政策原文人工确认'的软条件。用于回答'我离申报某资质还差什么/要补哪些'。"
            "门槛数值为结构性概要，请务必连同返回的 disclaimer 与 last_reviewed 一并告知用户；"
            "对'不达标/待确认/需人工确认'项，建议再调用 knowledge_base_search 取该资质对应政策"
            "原文交叉核对后再下结论。"
        ),
        parameters={
            "key": {
                "type": "string",
                "description": "资质唯一标识 key(如 high-tech-enterprise)，来自 qualification_list 返回项。",
            },
        },
        required=["key"],
    )
    async def qualification_gap(self, key: str) -> ToolResult[QualificationToolData]:
        """对指定资质做条件差距分析。"""
        key = (key or "").strip()
        if not key:
            return ToolResult(success=False, message="资质 key 不能为空")

        qual = self._by_key.get(key)
        if qual is None:
            return ToolResult(success=False, message=f"资质[{key}]不存在")

        tenant_id = await self._get_tenant_id()
        if not tenant_id:
            return ToolResult(success=False, message="当前会话缺少租户上下文，无法分析差距")

        profile = await self._load_profile(tenant_id) or EnterpriseProfile(tenant_id=tenant_id)
        report = analyze_gap(profile, qual)

        lines: List[str] = [f"{_STATUS_ICON[c.status]} {c.detail}" for c in report.checks]
        if report.prerequisites_missing:
            lines.append("缺失前置资质：" + "、".join(report.prerequisites_missing))
        if report.manual_review:
            lines.append("需结合材料/政策原文人工确认：")
            lines.extend(f"· {item}" for item in report.manual_review)

        return ToolResult(
            success=True,
            message=report.summary,
            data=QualificationToolData(
                kind="gap", title=f"{qual.name} 差距分析",
                summary=report.summary, lines=lines,
                disclaimer=qual.disclaimer, last_reviewed=qual.last_reviewed,
            ),
        )

    @tool(
        name="qualification_detail",
        description=(
            "取指定资质(由 key 指定)的申报详情：核心条件、主要材料、申报时间、政策依据、主要价值。"
            "用于回答'申报某资质需要准备哪些材料/什么时候申报/依据哪个文件'。材料与流程为结构性概要，"
            "请连同返回的 disclaimer 与 last_reviewed 告知用户，并建议结合 knowledge_base_search "
            "检索的政策原文给出最终的材料清单与办理流程。"
        ),
        parameters={
            "key": {
                "type": "string",
                "description": "资质唯一标识 key(如 high-tech-enterprise)，来自 qualification_list 返回项。",
            },
        },
        required=["key"],
    )
    async def qualification_detail(self, key: str) -> ToolResult[QualificationToolData]:
        """取指定资质的材料/流程/依据详情(目录静态数据，无需租户)。"""
        key = (key or "").strip()
        qual = self._by_key.get(key)
        if qual is None:
            return ToolResult(success=False, message=f"资质[{key}]不存在")

        lines: List[str] = []
        if qual.key_conditions:
            lines.append("核心条件：")
            lines.extend(f"· {c}" for c in qual.key_conditions)
        if qual.materials:
            lines.append("主要材料：")
            lines.extend(f"· {m}" for m in qual.materials)
        if qual.timing:
            lines.append(f"申报时间：{qual.timing}")
        if qual.policy_basis:
            lines.append(f"政策依据：{qual.policy_basis}")
        if qual.benefit:
            lines.append(f"主要价值：{qual.benefit}")

        return ToolResult(
            success=True,
            message=f"{qual.name} 申报详情",
            data=QualificationToolData(
                kind="detail", title=qual.name,
                summary=f"{qual.category}｜{qual.region}｜{qual.issuer}".strip("｜"),
                lines=lines,
                disclaimer=qual.disclaimer, last_reviewed=qual.last_reviewed,
            ),
        )
