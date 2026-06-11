import logging
from typing import List

from openai import AsyncOpenAI

from app.application.errors.exceptions import ServerRequestsError
from app.domain.external.embedding import EmbeddingProvider
from app.domain.models.app_config import EmbedConfig

logger = logging.getLogger(__name__)

# 单次请求最大输入条数。DashScope text-embedding-v3 兼容端点单批上限为 10。
MAX_BATCH_SIZE = 10


class OpenAIEmbedding(EmbeddingProvider):
    """基于 OpenAI 兼容端点的 Embedding 实现(默认对接 DashScope text-embedding-v3)"""

    def __init__(self, embed_config: EmbedConfig, api_key: str, **kwargs) -> None:
        """构造函数，api_key 由 .env 注入(优先)，回退到配置中的占位"""
        self._client = AsyncOpenAI(
            base_url=str(embed_config.base_url),
            api_key=api_key or embed_config.api_key,
            **kwargs,
        )
        self._model_name = embed_config.model_name
        self._dimension = embed_config.dimension
        self._timeout = 120

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量向量化，自动按 MAX_BATCH_SIZE 分批，保持输入顺序"""
        if not texts:
            return []

        vectors: List[List[float]] = []
        try:
            for start in range(0, len(texts), MAX_BATCH_SIZE):
                batch = texts[start:start + MAX_BATCH_SIZE]
                resp = await self._client.embeddings.create(
                    model=self._model_name,
                    input=batch,
                    timeout=self._timeout,
                )
                # 按 index 排序确保与输入顺序严格一致
                ordered = sorted(resp.data, key=lambda d: d.index)
                vectors.extend([d.embedding for d in ordered])
        except Exception as e:
            error_detail = f"{type(e).__name__}: {str(e) or '未知错误'}"
            logger.error(f"调用Embedding接口出错: {error_detail}, model={self._model_name}")
            raise ServerRequestsError(f"调用Embedding出错: {error_detail}")

        # 维度守卫：返回维度必须与配置(及 pgvector 列)一致
        if vectors and len(vectors[0]) != self._dimension:
            raise ServerRequestsError(
                f"Embedding 维度不一致: 返回 {len(vectors[0])} != 配置 {self._dimension}"
            )
        return vectors

    async def embed_query(self, text: str) -> List[float]:
        """单条查询向量化"""
        result = await self.embed_documents([text])
        return result[0] if result else []
