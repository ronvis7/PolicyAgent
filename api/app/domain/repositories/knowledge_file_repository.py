from typing import Protocol, Optional, List

from app.domain.models.knowledge_file import KnowledgeFile


class KnowledgeFileRepository(Protocol):
    """知识库文件数据仓库"""

    async def save(self, knowledge_file: KnowledgeFile) -> None:
        """新增或更新知识库文件"""
        ...

    async def get_by_id(self, file_id: str, tenant_id: Optional[str] = None) -> Optional[KnowledgeFile]:
        """根据id获取知识库文件(传入tenant_id则要求归属该租户)"""
        ...

    async def list_by_knowledge_base(self, kb_id: str, tenant_id: str) -> List[KnowledgeFile]:
        """列出某知识库下的全部文件(按创建时间倒序，要求归属该租户)"""
        ...

    async def delete(self, file_id: str, tenant_id: str) -> None:
        """删除知识库文件(级联删除其切片，要求归属该租户)"""
        ...
