"""评测数据集加载与向量工具（各能力评测共用）。"""

import json
import math
from pathlib import Path
from typing import Any, Sequence

DATASETS_DIR = Path(__file__).parent / "datasets"


def load_dataset(name: str) -> Any:
    """按文件名加载 datasets/ 下的 JSON 标注数据集（UTF-8）。"""
    path = DATASETS_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """两向量余弦相似度，镜像 pgvector 的距离排序口径（向量等长，零向量返回 0.0）。"""
    if len(a) != len(b):
        raise ValueError(f"向量维度不一致：{len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
