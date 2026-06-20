"""评测指标纯函数（无 IO，供各能力评测与复现脚本共用）。

只做最朴素、口径明确、可手工复核的指标实现，便于评委对照定义复算：
- 分类类（资质差距/截止抽取）：accuracy、按类目 precision/recall/F1、混淆计数；
- 排序检索类（RAG/政策匹配）：recall@k、precision@k、MRR、hit@k。
"""

from dataclasses import dataclass
from typing import Dict, Hashable, List, Sequence


# --------------------------------------------------------------------------- #
# 分类类指标（逐项预测 vs golden 标签）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClassificationReport:
    """多分类评测结果：总体准确率 + 每个标签的 precision/recall/F1。"""

    total: int
    correct: int
    per_label: Dict[str, Dict[str, float]]

    @property
    def accuracy(self) -> float:
        return _safe_div(self.correct, self.total)


def accuracy(predicted: Sequence[Hashable], golden: Sequence[Hashable]) -> float:
    """预测序列与 golden 序列逐项相等的比例。两序列必须等长。"""
    _require_same_length(predicted, golden)
    if not golden:
        return 0.0
    hits = sum(1 for p, g in zip(predicted, golden) if p == g)
    return _safe_div(hits, len(golden))


def classification_report(
    predicted: Sequence[Hashable], golden: Sequence[Hashable],
) -> ClassificationReport:
    """对多分类逐项预测计算总体准确率与每标签 precision/recall/F1。"""
    _require_same_length(predicted, golden)
    labels = sorted({str(x) for x in (*predicted, *golden)})
    per_label: Dict[str, Dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for p, g in zip(predicted, golden) if str(p) == label and str(g) == label)
        fp = sum(1 for p, g in zip(predicted, golden) if str(p) == label and str(g) != label)
        fn = sum(1 for p, g in zip(predicted, golden) if str(p) != label and str(g) == label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }
    correct = sum(1 for p, g in zip(predicted, golden) if p == g)
    return ClassificationReport(total=len(golden), correct=correct, per_label=per_label)


# --------------------------------------------------------------------------- #
# 排序/检索类指标（有序预测 id 列表 vs 相关 golden id 集合）
# --------------------------------------------------------------------------- #
def recall_at_k(ranked_ids: Sequence[Hashable], relevant: Sequence[Hashable], k: int) -> float:
    """前 k 个结果命中的相关项 / 全部相关项。relevant 为空返回 0.0。"""
    rel = set(relevant)
    if not rel:
        return 0.0
    hit = sum(1 for x in ranked_ids[:k] if x in rel)
    return _safe_div(hit, len(rel))


def precision_at_k(ranked_ids: Sequence[Hashable], relevant: Sequence[Hashable], k: int) -> float:
    """前 k 个结果中相关项的比例。k<=0 返回 0.0。"""
    if k <= 0:
        return 0.0
    rel = set(relevant)
    hit = sum(1 for x in ranked_ids[:k] if x in rel)
    return _safe_div(hit, k)


def hit_at_k(ranked_ids: Sequence[Hashable], relevant: Sequence[Hashable], k: int) -> float:
    """前 k 个结果是否至少命中一个相关项（命中=1.0，否则 0.0）。"""
    rel = set(relevant)
    return 1.0 if any(x in rel for x in ranked_ids[:k]) else 0.0


def reciprocal_rank(ranked_ids: Sequence[Hashable], relevant: Sequence[Hashable]) -> float:
    """第一个相关项排名的倒数（1-based）；未命中返回 0.0。"""
    rel = set(relevant)
    for idx, item in enumerate(ranked_ids, start=1):
        if item in rel:
            return 1.0 / idx
    return 0.0


def mean(values: Sequence[float]) -> float:
    """均值（空序列返回 0.0），用于跨用例聚合 recall@k/MRR 等。"""
    values = list(values)
    return _safe_div(sum(values), len(values))


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _require_same_length(a: Sequence, b: Sequence) -> None:
    if len(a) != len(b):
        raise ValueError(f"序列长度不一致：{len(a)} vs {len(b)}")
