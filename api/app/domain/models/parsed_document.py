from pydantic import BaseModel


class ParsedPage(BaseModel):
    """解析后的文档页，保留页码用于检索引用回溯"""
    page_number: int = 1  # 页码(从1开始；非分页格式如txt统一为1)
    text: str = ""  # 该页提取出的纯文本
