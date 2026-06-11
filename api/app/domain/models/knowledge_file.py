import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FileStatus(str, Enum):
    """知识库文件状态机(借鉴Yuxi)

    正常流转：uploaded -> parsing -> parsed -> indexing -> indexed
    异常分支：parsing阶段失败置error_parsing；indexing阶段失败置error_indexing
    """
    UPLOADED = "uploaded"  # 已上传(原始文件已落COS)
    PARSING = "parsing"  # 解析中
    PARSED = "parsed"  # 已解析(已提取文本/分块)
    INDEXING = "indexing"  # 向量化入库中
    INDEXED = "indexed"  # 已建立向量索引(可检索)
    ERROR_PARSING = "error_parsing"  # 解析失败
    ERROR_INDEXING = "error_indexing"  # 向量化失败


class KnowledgeFile(BaseModel):
    """知识库文件领域模型，记录上传到某知识库的单个文档及其处理状态"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 知识库文件id
    tenant_id: str = ""  # 所属租户id(多租户隔离，必填)
    knowledge_base_id: str = ""  # 所属知识库id(必填)
    owner_id: Optional[str] = None  # 上传者用户id
    file_id: Optional[str] = None  # 关联的原始文件id(files表，存COS对象)
    filename: str = ""  # 文件名(冗余存储，便于列表展示)
    status: FileStatus = FileStatus.UPLOADED  # 处理状态(状态机)
    error_message: str = ""  # 失败原因(status为error_*时填充)
    chunk_count: int = 0  # 切片数量
    updated_at: datetime = Field(default_factory=datetime.now)  # 更新时间
    created_at: datetime = Field(default_factory=datetime.now)  # 创建时间
