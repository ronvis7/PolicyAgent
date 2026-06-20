"""录制 RAG 检索评测的【真实向量快照】（一次性，需 embedding key）。

把 tests/eval/datasets/rag_retrieval.json 中的全部查询与切片文本，用与生产同一套
embedding（OpenAIEmbedding / text-embedding-v3）向量化，写入 datasets/rag_vectors.json。
此后离线评测对该冻结快照做余弦排序，确定可复现、无需再调网络。

用法（容器内，已注入 EMBED_API_KEY）：
    python scripts/record_rag_vectors.py
"""

import asyncio
import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from app.infrastructure.external.embedding.openai_embedding import OpenAIEmbedding  # noqa: E402
from app.infrastructure.repositories.file_app_config_repository import (  # noqa: E402
    FileAppConfigRepository,
)
from core.config import get_settings  # noqa: E402

_DATASET = _API_ROOT / "tests" / "eval" / "datasets" / "rag_retrieval.json"
_OUT = _API_ROOT / "tests" / "eval" / "datasets" / "rag_vectors.json"


def _build_embedder() -> OpenAIEmbedding:
    """与应用同源地组装平台 embedding（config.yaml + .env 的 EMBED_API_KEY）。"""
    settings = get_settings()
    embed_config = FileAppConfigRepository(settings.app_config_filepath).load().embed_config
    return OpenAIEmbedding(embed_config, api_key=settings.embed_api_key)


async def main() -> None:
    dataset = json.loads(_DATASET.read_text(encoding="utf-8"))
    embedder = _build_embedder()

    items = [("query", q["id"], q["text"]) for q in dataset["queries"]]
    items += [("chunk", c["id"], c["text"]) for c in dataset["chunks"]]
    vectors = await embedder.embed_documents([text for _, _, text in items])

    snapshot = {
        "model": embedder.model_name,
        "dimension": embedder.dimension,
        "vectors": {item_id: vec for (_, item_id, _), vec in zip(items, vectors)},
    }
    _OUT.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    print(f"已录制 {len(vectors)} 条向量（{embedder.model_name}, dim={embedder.dimension}） → {_OUT}")


if __name__ == "__main__":
    asyncio.run(main())
