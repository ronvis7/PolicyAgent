

from typing import Protocol, Optional

from app.domain.models.file import File


class FileRepository(Protocol):
    """文件模型数据仓库"""

    async def save(self, file: File) -> None:
        """新增或更新文件信息"""
        ...

    async def get_by_id(self, file_id: str, tenant_id: Optional[str] = None) -> Optional[File]:
        """根据文件id获取文件信息(传入tenant_id则要求归属该租户，否则返回None)"""
        ...
