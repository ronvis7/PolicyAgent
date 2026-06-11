import uuid
from typing import Any, Dict

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """文档切片领域模型，知识库文件分块后的最小检索单元

    注意：向量(embedding)是持久化与索引层的关注点，不作为领域字段，由
    DocumentChunkRepository 在写入/检索时单独承载，避免领域模型与
    pgvector/numpy 细节耦合(见 ADR-001：领域接口封装向量读写)。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 切片id
    tenant_id: str = ""  # 所属租户id(多租户隔离，必填)
    knowledge_base_id: str = ""  # 所属知识库id(必填)
    knowledge_file_id: str = ""  # 所属知识库文件id(必填)
    chunk_index: int = 0  # 切片在文件内的顺序索引(从0开始)
    content: str = ""  # 切片文本内容
    token_count: int = 0  # 切片token数(用于成本/截断控制)
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)  # 元数据(页码/位置等，供引用回答)
