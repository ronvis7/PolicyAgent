from typing import List

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
    """收藏单篇公开政策到私有政策库的请求体"""
    policy_id: str = Field(min_length=1, description="要收藏的公开政策id")


class CollectPoliciesRequest(BaseModel):
    """批量收藏公开政策到私有政策库的请求体"""
    policy_ids: List[str] = Field(min_length=1, max_length=100, description="要收藏的公开政策id列表")


class CollectPoliciesResult(BaseModel):
    """批量收藏结果：成功收藏与跳过(缺失/无正文)的数量"""
    collected_count: int = Field(description="成功收藏并已排队向量化的数量")
    skipped_count: int = Field(description="跳过的数量(政策不存在或正文为空)")
