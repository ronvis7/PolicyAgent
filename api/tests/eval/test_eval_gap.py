"""⑥ 资质差距分析效果评测（离线确定性门禁）。

对真实资质目录条目 × 标注企业档案跑 `analyze_gap`，把每条硬条件的预测状态与 golden
逐条比对，计算 逐条状态准确率 + 用例级精确匹配率；并单列"零误报不达标"纪律检查
（档案缺字段时绝不能判 unmet）。指标低于阈值即 fail，故本测试同时是评测与回归门禁。
"""

from datetime import date
from typing import Dict, List, Tuple

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.qualification import ConditionStatus
from app.domain.services.qualification_gap import analyze_gap
from app.infrastructure.data.qualification_catalog import load_qualification_catalog

from tests.eval import metrics
from tests.eval._support import load_dataset

_CATALOG = {q.key: q for q in load_qualification_catalog()}


def _parse_today(value: str) -> date:
    return date.fromisoformat(value)


def _predict_case(case: dict) -> Tuple[Dict[str, str], List[str]]:
    """对单个用例跑 analyze_gap，返回 {metric_value: status_value} 与缺失前置。"""
    qual = _CATALOG[case["qualification_key"]]
    profile = EnterpriseProfile(**case["profile"])
    report = analyze_gap(profile, qual, today=_parse_today(case["today"]))
    checks = {c.metric.value: c.status.value for c in report.checks}
    return checks, list(report.prerequisites_missing)


def evaluate() -> dict:
    """跑全量用例并聚合指标（供 pytest 与 run_eval.py 复用，返回可序列化 dict）。"""
    dataset = load_dataset("qualification_gap.json")
    cases = dataset["cases"]

    pred_states: List[str] = []
    gold_states: List[str] = []
    case_exact = 0
    fabricated_unmet = 0  # 档案缺字段却被判 unmet 的次数（纪律红线，应恒为 0）

    for case in cases:
        checks, prereq_missing = _predict_case(case)
        expected = case["expected"]
        exp_checks: Dict[str, str] = expected["checks"]

        case_ok = checks.keys() == exp_checks.keys()
        for metric_key, exp_status in exp_checks.items():
            got = checks.get(metric_key, "<missing>")
            pred_states.append(got)
            gold_states.append(exp_status)
            if got != exp_status:
                case_ok = False
            if exp_status == ConditionStatus.UNKNOWN.value and got == ConditionStatus.UNMET.value:
                fabricated_unmet += 1

        if sorted(prereq_missing) != sorted(expected["prerequisites_missing"]):
            case_ok = False
        if case_ok:
            case_exact += 1

    report = metrics.classification_report(pred_states, gold_states)
    return {
        "capability": "⑥ 资质差距分析",
        "cases": len(cases),
        "conditions": len(gold_states),
        "condition_accuracy": round(report.accuracy, 4),
        "case_exact_match": round(metrics._safe_div(case_exact, len(cases)), 4),
        "fabricated_unmet": fabricated_unmet,
        "per_label": report.per_label,
        "thresholds": dataset["meta"]["thresholds"],
    }


def test_qualification_gap_eval_meets_thresholds() -> None:
    result = evaluate()
    thresholds = result["thresholds"]

    assert result["condition_accuracy"] >= thresholds["condition_accuracy"], result
    assert result["case_exact_match"] >= thresholds["case_exact_match"], result
    # 风险纪律红线：缺字段绝不可误报"不达标"
    assert result["fabricated_unmet"] == 0, result
