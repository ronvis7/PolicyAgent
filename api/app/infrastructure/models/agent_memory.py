import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from ...domain.models.agent_memory import AgentMemory


class AgentMemoryModel(Base):
    """Agent 长期记忆条目 ORM（跨会话记忆第 2 层，按租户隔离）。

    每条记忆是一句自然语言事实/偏好；以 id 为主键、tenant_id 建索引作为召回/隔离边界。
    租户删除时记忆随之级联清理(ON DELETE CASCADE)。
    """
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # 所属租户id(召回与隔离边界)
    content: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''"),
    )  # 记忆内容(一句自然语言事实/偏好)
    source_session_id: Mapped[str] = mapped_column(String(255), nullable=True)  # 产生该记忆的会话id(溯源)
    created_by: Mapped[str] = mapped_column(String(255), nullable=True)  # 写入者用户id(溯源)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"),
    )

    @classmethod
    def from_domain(cls, memory: AgentMemory) -> "AgentMemoryModel":
        """从领域模型创建 ORM 模型。"""
        return cls(
            id=memory.id,
            tenant_id=memory.tenant_id,
            content=memory.content,
            source_session_id=memory.source_session_id,
            created_by=memory.created_by,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
        )

    def to_domain(self) -> AgentMemory:
        """将 ORM 模型转换为领域模型。"""
        return AgentMemory(
            id=self.id,
            tenant_id=self.tenant_id,
            content=self.content,
            source_session_id=self.source_session_id,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
