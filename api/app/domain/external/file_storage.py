from typing import Protocol, Tuple, BinaryIO, Optional

from fastapi import UploadFile

from app.domain.models.file import File


class FileStorage(Protocol):
    """文件存储桶协议"""

    async def upload_file(
            self,
            upload_file: UploadFile,
            tenant_id: Optional[str] = None,
            owner_id: Optional[str] = None,
    ) -> File:
        """根据传递的文件源上传文件后返回文件信息(可选标记租户与创建者)"""
        ...

    async def download_file(self, file_id: str) -> Tuple[BinaryIO, File]:
        """根据传递的文件id下载文件，并返回文件源+文件信息"""
        ...
