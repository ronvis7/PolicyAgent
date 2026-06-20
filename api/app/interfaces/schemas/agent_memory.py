"""Agent 长期记忆接口 schema（ADR 004）。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.domain.models.agent_memory import AgentMemory


class AgentMemoryItem(BaseModel):
    """单条长期记忆的对外表示。"""
    id: str
    content: str
    source_session_id: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_domain(cls, memory: AgentMemory) -> "AgentMemoryItem":
        return cls(
            id=memory.id,
            content=memory.content,
            source_session_id=memory.source_session_id,
            created_at=memory.created_at,
        )


class AgentMemoryListResponse(BaseModel):
    """长期记忆列表响应。"""
    items: List[AgentMemoryItem]
    total: int

    @classmethod
    def from_domain(cls, memories: List[AgentMemory]) -> "AgentMemoryListResponse":
        items = [AgentMemoryItem.from_domain(m) for m in memories]
        return cls(items=items, total=len(items))
