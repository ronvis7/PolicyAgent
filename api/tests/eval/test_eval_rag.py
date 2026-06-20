"""RAG 向量检索质量评测（离线确定性门禁）。

对每条查询，用【冻结的真实 embedding 向量快照】(rag_vectors.json，text-embedding-v3
录制) 与全部切片做余弦相似度排序（镜像 pgvector 的 `<=>` 距离序），按 golden 相关切片
计算 recall@3 / recall@5 / hit@1 / MRR（跨查询平均）。向量为真实模型产出、一次性冻结，
故评测既反映真实召回质量，又完全离线可复现。重新录制见 scripts/record_rag_vectors.py。
"""

from typing import List

from tests.eval import metrics
from tests.eval._support import cosine_similarity, load_dataset


def _rank_chunks(query_vec: List[float], chunk_ids: List[str], vectors: dict) -> List[str]:
    """按与查询向量的余弦相似度降序排列切片 id（确定性，平分时按 id 稳定排序）。"""
    scored = [
        (cid, cosine_similarity(query_vec, vectors[cid]))
        for cid in chunk_ids
    ]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [cid for cid, _ in scored]


def evaluate() -> dict:
    """跑全量查询并聚合检索指标（供 pytest 与 run_eval.py 复用）。"""
    dataset = load_dataset("rag_retrieval.json")
    snapshot = load_dataset("rag_vectors.json")
    vectors = snapshot["vectors"]
    chunk_ids = [c["id"] for c in dataset["chunks"]]

    recall3: List[float] = []
    recall5: List[float] = []
    hit1: List[float] = []
    rr: List[float] = []
    per_query = []

    for query in dataset["queries"]:
        ranked = _rank_chunks(vectors[query["id"]], chunk_ids, vectors)
        relevant = query["relevant"]
        r3 = metrics.recall_at_k(ranked, relevant, 3)
        r5 = metrics.recall_at_k(ranked, relevant, 5)
        h1 = metrics.hit_at_k(ranked, relevant, 1)
        mrr = metrics.reciprocal_rank(ranked, relevant)
        recall3.append(r3)
        recall5.append(r5)
        hit1.append(h1)
        rr.append(mrr)
        per_query.append({
            "query": query["id"],
            "top5": ranked[:5],
            "relevant": relevant,
            "recall@5": round(r5, 4),
            "rr": round(mrr, 4),
        })

    return {
        "capability": "RAG 向量检索质量",
        "queries": len(dataset["queries"]),
        "chunks": len(chunk_ids),
        "embedding_model": snapshot.get("model"),
        "dimension": snapshot.get("dimension"),
        "recall_at_3": round(metrics.mean(recall3), 4),
        "recall_at_5": round(metrics.mean(recall5), 4),
        "hit_at_1": round(metrics.mean(hit1), 4),
        "mrr": round(metrics.mean(rr), 4),
        "per_query": per_query,
        "thresholds": dataset["meta"]["thresholds"],
    }


def test_rag_retrieval_eval_meets_thresholds() -> None:
    result = evaluate()
    thresholds = result["thresholds"]

    assert result["recall_at_5"] >= thresholds["recall_at_5"], result
    assert result["mrr"] >= thresholds["mrr"], result
    assert result["hit_at_1"] >= thresholds["hit_at_1"], result
