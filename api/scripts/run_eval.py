"""核心能力效果评测一键复现入口。

跑全部四项离线确定性评测（⑥资质差距 / ⑤截止抽取 / RAG检索 / ③政策匹配），在终端打印
指标汇总，并把结果连同数据集说明、指标定义、复现命令写入 docs/competition/评测报告.md。

用法（容器内或装好 api/requirements.txt 的环境，工作目录 = api/）：
    python scripts/run_eval.py            # 跑评测 + 刷新报告
    python scripts/run_eval.py --no-report  # 只打印，不写报告

数据集与冻结快照见 tests/eval/datasets/；RAG 真实向量重录见 scripts/record_rag_vectors.py。
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _API_ROOT.parent
sys.path.insert(0, str(_API_ROOT))

from tests.eval import test_eval_deadline, test_eval_gap, test_eval_matching, test_eval_rag  # noqa: E402

_REPORT_PATH = _REPO_ROOT / "docs" / "competition" / "评测报告.md"


def _run_all() -> dict:
    """依次跑四项评测，返回 {capability_slug: result}。"""
    return {
        "gap": test_eval_gap.evaluate(),
        "deadline": test_eval_deadline.evaluate(),
        "rag": test_eval_rag.evaluate(),
        "matching": test_eval_matching.evaluate(),
    }


def _print_summary(results: dict) -> None:
    print("\n==================== 核心能力效果评测汇总 ====================\n")
    for result in results.values():
        print(f"# {result['capability']}")
        for key, value in result.items():
            if key in {"capability", "per_label", "per_query", "per_profile", "thresholds"}:
                continue
            print(f"    {key}: {value}")
        print()


def _fmt_thresholds(thresholds: dict) -> str:
    # 编造率/误命中类为上界（越小越好），其余为下界
    return "、".join(
        f"{k} {'≤' if ('rate' in k or 'fabricat' in k) else '≥'} {v}"
        for k, v in thresholds.items()
    )


def _build_report(results: dict) -> str:
    gap, deadline, rag, matching = (
        results["gap"], results["deadline"], results["rag"], results["matching"]
    )
    lines = [
        "# PolicyManus 核心能力效果评测报告",
        "",
        "> 本报告由 `api/scripts/run_eval.py` 自动生成，对照比赛要求「可验证的测试结果"
        "（含测试数据集、评测指标及复现脚本），确保核心结果可复现」。",
        f"> 生成日期：{date.today().isoformat()}",
        "",
        "## 一、评测对象与方法",
        "",
        "评测覆盖产品四项核心 AI 能力，全部走**离线确定性**口径——纯函数直接评测，"
        "真实 LLM/Embedding 调用只在录制冻结快照时发生，故任何人 clone 仓库后一条命令即可"
        "复现同一组数字，无需密钥、不依赖网络。",
        "",
        "| 能力 | 数据集 | 评测内核 | 主要指标 |",
        "|---|---|---|---|",
        "| ⑥ 资质差距分析 | `qualification_gap.json` | `analyze_gap`（纯函数） | 逐条状态准确率 / 用例精确匹配率 |",
        "| ⑤ 申报截止抽取 | `deadline_extraction.json` | `parse_extraction_result`（纪律层） | 状态准确率 / 日期精确率 / 编造率 |",
        "| RAG 向量检索 | `rag_retrieval.json` + `rag_vectors.json`（真实向量快照） | 余弦排序 | recall@k / hit@1 / MRR |",
        "| ③ 政策匹配 | `policy_matching.json` | `structured_score`（纯函数） | recall@3 / hit@1 / MRR |",
        "",
        "## 二、评测结果",
        "",
        "### ⑥ 资质差距分析",
        "",
        f"- 用例数 **{gap['cases']}**、核验条件数 **{gap['conditions']}**",
        f"- 逐条状态准确率 **{gap['condition_accuracy']}**、用例精确匹配率 **{gap['case_exact_match']}**",
        f"- 风险纪律红线·缺字段误报不达标次数 **{gap['fabricated_unmet']}**（应为 0）",
        f"- 达标阈值：{_fmt_thresholds(gap['thresholds'])}",
        "",
        "### ⑤ 申报截止抽取",
        "",
        f"- 用例数 **{deadline['cases']}**",
        f"- 状态准确率 **{deadline['status_accuracy']}**、抽取日期精确率 **{deadline['deadline_exact']}**",
        f"- 风险纪律红线·编造率 **{deadline['fabrication_rate']}**（应为 0，即绝不无中生有地给出截止日期）",
        f"- 达标阈值：{_fmt_thresholds(deadline['thresholds'])}",
        "",
        "### RAG 向量检索",
        "",
        f"- 查询数 **{rag['queries']}**、切片数 **{rag['chunks']}**、"
        f"向量模型 **{rag['embedding_model']}**（{rag['dimension']} 维，真实快照）",
        f"- recall@3 **{rag['recall_at_3']}**、recall@5 **{rag['recall_at_5']}**、"
        f"hit@1 **{rag['hit_at_1']}**、MRR **{rag['mrr']}**",
        f"- 达标阈值：{_fmt_thresholds(rag['thresholds'])}",
        "",
        "### ③ 政策匹配（结构化命中路）",
        "",
        f"- 档案数 **{matching['profiles']}**、政策池 **{matching['policies']}**",
        f"- recall@3 **{matching['recall_at_3']}**、hit@1 **{matching['hit_at_1']}**、MRR **{matching['mrr']}**",
        f"- 干扰项误命中次数 **{matching['distractor_false_hits']}**（无关政策结构化得分应为 0）",
        f"- 达标阈值：{_fmt_thresholds(matching['thresholds'])}",
        "",
        "## 三、复现方式",
        "",
        "```bash",
        "# 1. 安装后端依赖（Python 3.12）",
        "cd api && pip install -r requirements.txt && pip install 'pytest>=9.0.2'",
        "",
        "# 2a. 一键复现全部指标并刷新本报告",
        "python scripts/run_eval.py",
        "",
        "# 2b. 或以 pytest 门禁形式运行（指标低于阈值即 fail，CI 同款）",
        "pytest tests/eval -q",
        "",
        "# （可选）用真实 embedding 重新录制 RAG 向量快照（需 EMBED_API_KEY）",
        "python scripts/record_rag_vectors.py",
        "```",
        "",
        "所有评测已纳入 CI（`.github/workflows/ci.yml` 的 backend job 跑 `pytest tests`），"
        "每次提交自动校验核心能力指标不回退。",
        "",
        "## 四、数据集说明",
        "",
        "数据集位于 `api/tests/eval/datasets/`，均为 UTF-8 JSON，含 `meta` 字段记录"
        "数据来源、标注口径、确定性说明与达标阈值：",
        "",
        "- `qualification_gap.json`：企业档案 × **真实资质目录条目**"
        "（`app.infrastructure.data.qualification_catalog`）的差距分析 golden 标注。",
        "- `deadline_extraction.json`：政策正文 + **冻结的模型输出快照** + golden 截止判定，"
        "重点覆盖『待核对纪律』边界（非法/脏数据 → 安全降级，绝不编造）。",
        "- `rag_retrieval.json` + `rag_vectors.json`：惠企政策领域查询/切片语料 + 人工相关性标注 "
        "+ 真实 embedding 向量快照（一次性录制后冻结）。",
        "- `policy_matching.json`：受控政策语料（主题/地区单一、相关性客观）+ 档案相关性标注。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="核心能力效果评测一键复现")
    parser.add_argument("--no-report", action="store_true", help="只打印指标，不写评测报告")
    args = parser.parse_args()

    results = _run_all()
    _print_summary(results)

    if not args.no_report:
        _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _REPORT_PATH.write_text(_build_report(results), encoding="utf-8")
        print(f"评测报告已写入：{_REPORT_PATH}")

    # 所有阈值均满足才返回 0，便于脚本/CI 直接以退出码判定
    ok = all(_thresholds_met(r) for r in results.values())
    return 0 if ok else 1


def _thresholds_met(result: dict) -> bool:
    """按结果里的 thresholds 逐项校验（≥ 阈值；编造率/误命中类为 ≤）。"""
    thresholds = result.get("thresholds", {})
    for key, bound in thresholds.items():
        value = result.get(key)
        if value is None:
            continue
        if "rate" in key or "fabricat" in key:
            if value > bound:
                return False
        elif value < bound:
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
