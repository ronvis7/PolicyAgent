import logging
from typing import List

import pymupdf
from starlette.concurrency import run_in_threadpool

from app.application.errors.exceptions import ServerRequestsError
from app.domain.external.document_parser import DocumentParser
from app.domain.models.parsed_document import ParsedPage

logger = logging.getLogger(__name__)

# 支持的扩展名(小写含点)
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


class PyMuPDFParser(DocumentParser):
    """基于 PyMuPDF 的文档解析器，PDF 按页提取文本，txt/md 作单页处理"""

    def supports(self, extension: str) -> bool:
        return extension.lower() in SUPPORTED_EXTENSIONS

    async def parse(self, content: bytes, extension: str) -> List[ParsedPage]:
        ext = extension.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ServerRequestsError(f"暂不支持解析该文件类型: {extension}")

        if ext in {".txt", ".md"}:
            return [ParsedPage(page_number=1, text=self._decode_text(content))]

        # PDF 解析为 CPU 密集型，放到线程池避免阻塞事件循环
        return await run_in_threadpool(self._parse_pdf, content)

    @staticmethod
    def _decode_text(content: bytes) -> str:
        """解码文本文件，优先 utf-8，回退 gbk(中文政策文档常见)"""
        for encoding in ("utf-8", "gbk"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore")

    @staticmethod
    def _parse_pdf(content: bytes) -> List[ParsedPage]:
        """逐页提取 PDF 文本"""
        pages: List[ParsedPage] = []
        try:
            with pymupdf.open(stream=content, filetype="pdf") as doc:
                for i, page in enumerate(doc):
                    pages.append(ParsedPage(page_number=i + 1, text=page.get_text()))
        except Exception as e:
            logger.error(f"PDF 解析失败: {type(e).__name__}: {e}")
            raise ServerRequestsError(f"PDF 解析失败: {e}")
        return pages
