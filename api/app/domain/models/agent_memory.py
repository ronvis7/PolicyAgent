import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentMemory(BaseModel):
    """Agent 长期记忆条目领域模型（跨会话记忆第 2 层）。

    每条记忆是一句自然语言事实/偏好（如"该企业 2026 年新增 3 项发明专利"、
    "用户偏好简洁、不要列表"），按租户聚合。会话启动时取最近若干条渲染进系统
    提示词，让 Agent 跨会话"记得"用户说过的事。`source_session_id`/`created_by`
    仅作溯源，隔离与召回均以 `tenant_id` 为边界。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 记忆条目id
    tenant_id: str = ""  # 所属租户id(隔离与召回边界)
    content: str = ""  # 记忆内容(一句自然语言事实/偏好)
    source_session_id: Optional[str] = None  # 产生该记忆的会话id(溯源)
    created_by: Optional[str] = None  # 写入者用户id(溯源)
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
