from typing import Protocol, List

from app.domain.models.parsed_document import ParsedPage


class DocumentParser(Protocol):
    """文档解析器接口，将原始文件字节解析为带页码的文本页列表"""

    def supports(self, extension: str) -> bool:
        """判断是否支持该扩展名(含点，如 '.pdf')"""
        ...

    async def parse(self, content: bytes, extension: str) -> List[ParsedPage]:
        """将文件字节解析为文本页列表(按页码顺序)"""
        ...
