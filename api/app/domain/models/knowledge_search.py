from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeCitation(BaseModel):
    """检索命中的知识库切片引用，供引用回答与前端来源卡片渲染

    页码/文件名来自切片的归属信息(chunk_metadata 的 page + 回查 KnowledgeFile 的
    filename)，是 R3「带引用回答」的最小事实单元。
    """
    chunk_id: str = ""  # 切片id
    knowledge_base_id: str = ""  # 所属知识库id
    knowledge_file_id: str = ""  # 所属知识库文件id
    filename: str = ""  # 来源文件名(回查 KnowledgeFile 得到)
    page: Optional[int] = None  # 来源页码(PDF 适用，txt/md 为 1)
    content: str = ""  # 命中切片文本(可能为节选)
    score: float = 0.0  # 相似度(越大越相关)


class KnowledgeSearchResults(BaseModel):
    """knowledge_base_search 工具的结构化结果"""
    query: str = ""  # 本次检索查询
    citations: List[KnowledgeCitation] = Field(default_factory=list)  # 命中引用列表(按相似度倒序)
