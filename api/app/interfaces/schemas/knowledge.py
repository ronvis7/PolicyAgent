from pydantic import BaseModel, Field

from app.domain.models.knowledge_base import KnowledgeBaseType


class CreateKnowledgeBaseRequest(BaseModel):
    """新建知识库请求体"""
    name: str = Field(min_length=1, max_length=255, description="知识库名称")
    description: str = Field(default="", max_length=1024, description="知识库描述")
    type: KnowledgeBaseType = Field(
        default=KnowledgeBaseType.GENERAL,
        description="知识库类型：general=通用文档库 / policy=私有政策库(收藏公开政策)",
    )


class CollectPolicyRequest(BaseModel):
    """收藏公开政策到私有政策库的请求体"""
    policy_id: str = Field(min_length=1, description="要收藏的公开政策id")
