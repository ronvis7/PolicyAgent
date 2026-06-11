from pydantic import BaseModel, Field


class CreateKnowledgeBaseRequest(BaseModel):
    """新建知识库请求体"""
    name: str = Field(min_length=1, max_length=255, description="知识库名称")
    description: str = Field(default="", max_length=1024, description="知识库描述")
