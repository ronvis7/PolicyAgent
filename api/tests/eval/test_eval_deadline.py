"""⑤ 申报截止抽取效果评测（离线确定性门禁 + 可选 --live 端到端）。

离线门禁评测**确定性的『待核对纪律』决策层** `parse_extraction_result`：对每条冻结的
模型原始输出快照解析，比对 golden（该输出下纪律层应得的判定）。重点验证：
- 正常抽取/常年受理/无截止 的状态判定正确；
- 纪律红线——模型声称 found 却给非法/空日期、脏 JSON、空返回 一律安全回退 unknown，
  **绝不编造日期**（fabrication_rate 必须为 0）。

真实端到端准确率（LLM 抽取）由 `scripts/run_eval.py --live` 在有 key 时复现，不进 CI。
"""

from app.domain.services.deadline_extractor import parse_extraction_result

from tests.eval import metrics
from tests.eval._support import load_dataset


def _predict_offline(model_output: str) -> tuple[str, str | None]:
    """跑确定性纪律层，返回 (status, deadline_iso | None)。"""
    result = parse_extraction_result(model_output)
    deadline = result.deadline.isoformat() if result.deadline else None
    return result.status, deadline


def evaluate() -> dict:
    """离线评测全量用例并聚合指标（供 pytest 与 run_eval.py 复用）。"""
    dataset = load_dataset("deadline_extraction.json")
    cases = dataset["cases"]

    pred_status: list[str] = []
    gold_status: list[str] = []
    extracted_total = 0
    extracted_date_hit = 0
    fabrications = 0  # golden 非 extracted 却被判出具体日期（纪律红线）

    for case in cases:
        status, deadline = _predict_offline(case["model_output"])
        gold = case["golden"]
        pred_status.append(status)
        gold_status.append(gold["status"])

        if gold["status"] == "extracted":
            extracted_total += 1
            if status == "extracted" and deadline == gold["deadline"]:
                extracted_date_hit += 1
        elif status == "extracted" and deadline is not None:
            fabrications += 1

    report = metrics.classification_report(pred_status, gold_status)
    return {
        "capability": "⑤ 申报截止抽取（纪律层）",
        "cases": len(cases),
        "status_accuracy": round(report.accuracy, 4),
        "deadline_exact": round(metrics._safe_div(extracted_date_hit, extracted_total), 4),
        "fabrication_rate": round(metrics._safe_div(fabrications, len(cases)), 4),
        "per_label": report.per_label,
        "thresholds": dataset["meta"]["thresholds"],
    }


def test_deadline_extraction_eval_meets_thresholds() -> None:
    result = evaluate()
    thresholds = result["thresholds"]

    assert result["status_accuracy"] >= thresholds["status_accuracy"], result
    assert result["deadline_exact"] >= thresholds["deadline_exact"], result
    # 风险纪律红线：绝不编造日期
    assert result["fabrication_rate"] <= thresholds["fabrication_rate"], result
