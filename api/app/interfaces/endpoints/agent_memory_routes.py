"""Agent 长期记忆路由：查看/删除当前组织的跨会话记忆（ADR 004）。

让用户看到"Agent 记住了关于本企业的什么"并可删除。记忆的写入由 Agent 在对话中
通过 MemoryTool 自主完成，此处只读/删。所有操作限当前登录租户。
"""

import logging

from fastapi import APIRouter, Depends

from app.application.services.agent_memory_service import AgentMemoryService
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas.agent_memory import AgentMemoryListResponse
from app.interfaces.schemas.base import Response
from app.interfaces.service_dependencies import get_agent_memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-memories", tags=["Agent记忆"])


@router.get(
    path="",
    response_model=Response[AgentMemoryListResponse],
    summary="列出当前组织的 Agent 长期记忆",
    description="返回 Agent 在历次会话中为当前企业记下的长期记忆，按时间倒序。租户内成员均可查看。",
)
async def list_agent_memories(
        current_user: CurrentUser = Depends(get_current_user),
        service: AgentMemoryService = Depends(get_agent_memory_service),
) -> Response[AgentMemoryListResponse]:
    """列出当前组织的 Agent 长期记忆"""
    memories = await service.list_memories(current_user.tenant_id)
    return Response.success(data=AgentMemoryListResponse.from_domain(memories))


@router.delete(
    path="/{memory_id}",
    response_model=Response[dict],
    summary="删除一条 Agent 长期记忆",
    description="删除当前组织下指定的长期记忆条目；不属于当前租户的 id 视为未找到。",
)
async def delete_agent_memory(
        memory_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        service: AgentMemoryService = Depends(get_agent_memory_service),
) -> Response[dict]:
    """删除当前组织的一条 Agent 长期记忆"""
    deleted = await service.delete_memory(current_user.tenant_id, memory_id)
    if not deleted:
        return Response.fail(code=404, msg="记忆不存在或无权删除")
    return Response.success(msg="删除记忆成功")
