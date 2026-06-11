"""文本分块(chunking)纯逻辑：按页切分为带重叠的切片，保留页码元数据供引用回答。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.domain.models.parsed_document import ParsedPage

# 分块参数(字符数)。政策文档以中文为主，1000 字约 600-700 token，留 150 重叠保上下文连续。
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


@dataclass
class ChunkPiece:
    """一个切片片段(尚未带 kb/file/tenant 归属，由应用层补全)"""
    content: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


def _split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """将单段文本按固定窗口+重叠切分；步进至少为1，避免死循环"""
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    step = max(1, chunk_size - overlap)
    pieces: List[str] = []
    for start in range(0, len(cleaned), step):
        segment = cleaned[start:start + chunk_size].strip()
        if segment:
            pieces.append(segment)
        if start + chunk_size >= len(cleaned):
            break
    return pieces


def chunk_pages(
    pages: List[ParsedPage],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[ChunkPiece]:
    """将解析后的页列表切分为全局顺序编号的切片，逐页切分以保留页码"""
    chunks: List[ChunkPiece] = []
    index = 0
    for page in pages:
        for segment in _split_text(page.text, chunk_size, overlap):
            chunks.append(
                ChunkPiece(
                    content=segment,
                    chunk_index=index,
                    token_count=max(1, len(segment) // 4),  # 粗略 token 估算
                    metadata={"page": page.page_number},
                )
            )
            index += 1
    return chunks
