"""长期记忆工具（Agent 跨会话记忆第 2 层的"写入"半边）。

给 Agent 一个显式的"记忆"能力：当用户在对话中陈述了**值得长期记住**的事实或偏好
（如经营数据变化、申报意向、答复风格偏好）时，Agent 主动调用 `memory_save` 把它
写入当前企业(租户)的长期记忆；下次新会话启动时这些记忆会被自动注入系统提示词召回。
另提供 `memory_list` 让 Agent 按需查看已记下的内容。

设计要点（对齐 QualificationTool）：
- 仅依赖 domain 模型 + uow 读写，不碰 application/infrastructure，保持分层。
- 租户范围由会话懒加载得到，作为隔离与归属边界。
- 写入前对已有记忆做**规范化精确去重**，避免反复记同一句。
"""

import logging
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from app.domain.models.agent_memory import AgentMemory
from app.domain.models.tool_result import ToolResult
from app.domain.repositories.uow import IUnitOfWork
from .base import BaseTool, tool

logger = logging.getLogger(__name__)

# 单条记忆内容长度上限(防止把整段对话塞进来当一条记忆)
_MAX_CONTENT_LEN = 500
# memory_list 返回的最大条数
_LIST_LIMIT = 50


class MemoryToolData(BaseModel):
    """记忆工具统一返回体(供 LLM 观察与前端卡片渲染)。"""
    kind: str  # save | list
    summary: str = ""  # 一句话总览
    lines: List[str] = Field(default_factory=list)  # 人读要点(已保存内容或记忆清单)


def _normalize(text: str) -> str:
    """记忆内容规范化(用于精确去重)：去首尾空白、合并内部空白、转小写。"""
    return " ".join((text or "").split()).lower()


class MemoryTool(BaseTool):
    """长期记忆工具集(跨会话记忆第 2 层)。"""
    name: str = "memory"

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        session_id: str,
    ) -> None:
        """构造函数，注入 uow 工厂与会话上下文。"""
        super().__init__()
        self._uow_factory = uow_factory
        self._session_id = session_id
        # 会话租户与归属用户懒加载缓存(隔离边界)
        self._tenant_id: Optional[str] = None
        self._owner_id: Optional[str] = None
        self._scope_loaded = False

    async def _load_scope(self) -> None:
        """懒加载当前会话所属租户与创建者，作为记忆归属/隔离边界。"""
        if not self._scope_loaded:
            async with self._uow_factory() as uow:
                session = await uow.session.get_by_id(self._session_id)
            if session:
                self._tenant_id = session.tenant_id
                self._owner_id = session.owner_id
            self._scope_loaded = True

    @tool(
        name="memory_save",
        description=(
            "把一条**值得长期记住**的关于当前企业(用户)的事实或偏好写入长期记忆，使其在以后的"
            "**新会话**中也能被你自动想起。适用场景：用户陈述了相对稳定、跨会话有用的信息——例如"
            "经营/研发数据的变化、明确的申报意向或优先级、对答复风格的偏好(如'回答简洁些')、"
            "需要长期跟进的事项。**只记真正有长期价值的要点，一次一条、用简洁的陈述句**；"
            "不要记一次性的闲聊、临时问题或已在企业档案里的结构化字段。"
        ),
        parameters={
            "content": {
                "type": "string",
                "description": "要长期记住的一条事实/偏好，简洁的陈述句(如：该企业2026年新增3项发明专利)。",
            },
        },
        required=["content"],
    )
    async def memory_save(self, content: str) -> ToolResult[MemoryToolData]:
        """写入一条长期记忆(同租户精确去重)。"""
        content = (content or "").strip()
        if not content:
            return ToolResult(success=False, message="记忆内容不能为空")
        if len(content) > _MAX_CONTENT_LEN:
            content = content[:_MAX_CONTENT_LEN].rstrip()

        await self._load_scope()
        if not self._tenant_id:
            return ToolResult(success=False, message="当前会话缺少租户上下文，无法写入记忆")

        async with self._uow_factory() as uow:
            existing = await uow.agent_memory.list_by_tenant(self._tenant_id)
            if any(_normalize(m.content) == _normalize(content) for m in existing):
                return ToolResult(
                    success=True,
                    message="该记忆此前已记录，无需重复",
                    data=MemoryToolData(kind="save", summary="这条信息我已经记住了，无需重复记录。"),
                )
            await uow.agent_memory.add(AgentMemory(
                tenant_id=self._tenant_id,
                content=content,
                source_session_id=self._session_id,
                created_by=self._owner_id,
            ))

        logger.info(f"写入长期记忆, 租户: {self._tenant_id}, 内容: {content[:50]}...")
        return ToolResult(
            success=True,
            message="已记入长期记忆",
            data=MemoryToolData(kind="save", summary="已记住", lines=[content]),
        )

    @tool(
        name="memory_list",
        description=(
            "列出你为当前企业(用户)记下的长期记忆条目。当你需要回顾'我之前记住过关于这个用户的"
            "什么信息'时调用。会话启动时这些记忆通常已注入上下文，仅在需要显式核对时才调用本工具。"
        ),
        parameters={},
        required=[],
    )
    async def memory_list(self) -> ToolResult[MemoryToolData]:
        """列出当前租户的长期记忆条目。"""
        await self._load_scope()
        if not self._tenant_id:
            return ToolResult(success=False, message="当前会话缺少租户上下文，无法读取记忆")

        async with self._uow_factory() as uow:
            memories = await uow.agent_memory.list_by_tenant(self._tenant_id, limit=_LIST_LIMIT)

        if not memories:
            return ToolResult(
                success=True,
                message="暂无长期记忆",
                data=MemoryToolData(kind="list", summary="目前还没有为该企业记录任何长期记忆。"),
            )

        lines = [m.content for m in memories if m.content.strip()]
        return ToolResult(
            success=True,
            message=f"共 {len(lines)} 条长期记忆",
            data=MemoryToolData(
                kind="list",
                summary=f"已为该企业记录 {len(lines)} 条长期记忆。",
                lines=lines,
            ),
        )
