from typing import Protocol, Optional, List

from app.domain.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository(Protocol):
    """知识库数据仓库"""

    async def save(self, knowledge_base: KnowledgeBase) -> None:
        """新增或更新知识库"""
        ...

    async def get_by_id(self, kb_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeBase]:
        """根据id获取知识库(传入tenant_id则要求归属该租户)"""
        ...

    async def list_by_tenant(self, tenant_id: str) -> List[KnowledgeBase]:
        """列出某租户下的全部知识库(按创建时间倒序)"""
        ...

    async def delete(self, kb_id: str, tenant_id: str) -> None:
        """删除知识库(级联删除其文件与切片，要求归属该租户)"""
        ...
