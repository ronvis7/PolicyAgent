"""③ 政策匹配效果评测（结构化命中路，离线确定性门禁）。

对每个企业档案，用 `structured_score` 给政策池逐篇打分并降序排序，按 golden 相关政策
计算 recall@3 / hit@1 / MRR（跨档案平均）；并校验无关政策（农业/文旅/商贸等干扰项）
得分恒为 0（零误命中）。structured_score 为纯函数（jieba 确定），评测离线可复现。

说明：线上 ③ 还融合语义召回(RRF)，此处仅评测结构化命中这一路；语义召回质量见 RAG 评测。
"""

from typing import List

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.policy import Policy
from app.domain.services.policy_matcher import structured_score

from tests.eval import metrics
from tests.eval._support import load_dataset


def _rank_policies(profile: EnterpriseProfile, policies: List[Policy]) -> List[tuple]:
    """按 structured_score 降序排序，返回 [(policy_id, score)]（平分按 id 稳定）。"""
    scored = [(p.id, structured_score(profile, p)[0]) for p in policies]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return scored


def evaluate() -> dict:
    """跑全量档案并聚合匹配指标（供 pytest 与 run_eval.py 复用）。"""
    dataset = load_dataset("policy_matching.json")
    policies = [Policy(**p) for p in dataset["policies"]]
    all_relevant = {pid for prof in dataset["profiles"] for pid in prof["relevant"]}
    distractor_ids = {p.id for p in policies} - all_relevant

    recall3: List[float] = []
    hit1: List[float] = []
    rr: List[float] = []
    distractor_hits = 0  # 干扰项被打出非零分的次数（应为 0）
    per_profile = []

    for prof in dataset["profiles"]:
        profile = EnterpriseProfile(**prof["profile"])
        scored = _rank_policies(profile, policies)
        ranked = [pid for pid, _ in scored]
        relevant = prof["relevant"]

        distractor_hits += sum(
            1 for pid, score in scored if pid in distractor_ids and score > 0
        )
        r3 = metrics.recall_at_k(ranked, relevant, 3)
        h1 = metrics.hit_at_k(ranked, relevant, 1)
        mrr = metrics.reciprocal_rank(ranked, relevant)
        recall3.append(r3)
        hit1.append(h1)
        rr.append(mrr)
        per_profile.append({
            "profile": prof["id"],
            "top3": ranked[:3],
            "relevant": relevant,
            "recall@3": round(r3, 4),
            "rr": round(mrr, 4),
        })

    return {
        "capability": "③ 政策匹配（结构化命中）",
        "profiles": len(dataset["profiles"]),
        "policies": len(policies),
        "recall_at_3": round(metrics.mean(recall3), 4),
        "hit_at_1": round(metrics.mean(hit1), 4),
        "mrr": round(metrics.mean(rr), 4),
        "distractor_false_hits": distractor_hits,
        "per_profile": per_profile,
        "thresholds": dataset["meta"]["thresholds"],
    }


def test_policy_matching_eval_meets_thresholds() -> None:
    result = evaluate()
    thresholds = result["thresholds"]

    assert result["recall_at_3"] >= thresholds["recall_at_3"], result
    assert result["mrr"] >= thresholds["mrr"], result
    assert result["hit_at_1"] >= thresholds["hit_at_1"], result
    # 干扰项零误命中（无关政策不应被结构化命中打分）
    assert result["distractor_false_hits"] == 0, result
