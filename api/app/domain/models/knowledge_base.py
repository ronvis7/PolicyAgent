import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeBaseType(str, Enum):
    """知识库类型枚举(用于可插拔KnowledgeBase工厂选择具体实现)"""
    GENERAL = "general"  # 通用向量检索知识库(R1默认实现)


class KnowledgeBase(BaseModel):
    """知识库领域模型，一个租户下可建多个知识库，是文件与切片的归属边界"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 知识库id
    tenant_id: str = ""  # 所属租户id(多租户隔离，必填)
    owner_id: Optional[str] = None  # 创建者用户id
    name: str = ""  # 知识库名称
    description: str = ""  # 知识库描述
    type: KnowledgeBaseType = KnowledgeBaseType.GENERAL  # 知识库类型(工厂分发)
    is_public: bool = False  # 是否为全局公开库(跨租户共享，如公开政策库)
    embedding_model: str = ""  # 该库使用的embedding模型名(切片向量与之绑定)
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
