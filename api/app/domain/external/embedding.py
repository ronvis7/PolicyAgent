from typing import Protocol, List


class EmbeddingProvider(Protocol):
    """文本向量化(Embedding)提供商接口

    实现可对接 API(text-embedding-v3)或未来本地模型(bge-m3)，应用层不感知具体后端。
    """

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量将文档切片文本向量化，返回与输入等长、顺序一致的向量列表"""
        ...

    async def embed_query(self, text: str) -> List[float]:
        """将单条查询文本向量化(用于检索)"""
        ...

    @property
    def dimension(self) -> int:
        """只读属性，返回向量维度(须与 pgvector 列维度一致)"""
        ...

    @property
    def model_name(self) -> str:
        """只读属性，返回 embedding 模型名"""
        ...
