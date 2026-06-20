# 核心能力效果评测工程（比赛第3项：可复现测试结果）

Issue：—
分支：`feat/eval-harness` → 已合并 main（merge `85a581f`）；服务器 override 跟踪 → `d8b09fb`
负责人：—
更新时间：2026-06-20

## 目标

满足 Agent 比赛电子文件第(3)项「可验证的测试结果：测试数据集 + 评测指标 + 复现脚本，
确保核心结果可复现」。既有 288 单测只证明"功能正确"，本工程补"AI 效果有多好"的量化证据。
验收：四项核心能力各有标注数据集 + 量化指标 + 一键复现，全部离线确定、纳入 CI。

## 已完成

新增 `api/tests/eval/`（效果评测，区别于 `tests/app` 功能单测），四项能力全部**离线确定性**：

- **⑥ 资质差距** `analyze_gap`：`datasets/qualification_gap.json` 14 用例/26 条件（真实资质目录），
  状态准确率 **1.0**、用例精确匹配 **1.0**、缺字段误报不达标 **0**。
- **⑤ 截止抽取** `parse_extraction_result`（纪律层）：`deadline_extraction.json` 12 用例，
  状态/日期准确率 **1.0**、**编造率 0**；真实端到端走 `--live`（需 LLM key）。
- **RAG 检索**：`rag_retrieval.json`（5 查询/15 切片）+ `rag_vectors.json`（**冻结的真实
  text-embedding-v3 向量快照，1024 维**），余弦排序 recall@3/@5 **1.0**、hit@1 **1.0**、MRR **1.0**。
- **③ 政策匹配** `structured_score`：`policy_matching.json`（受控语料、相关性客观）
  recall@3 **1.0**、MRR **1.0**、干扰项零误命中。

支撑件：`metrics.py`（accuracy/precision/recall/recall@k/MRR/分类报告 纯函数）、`_support.py`
（数据集加载 + 余弦）、`scripts/run_eval.py`（一键跑全部 + 生成报告，退出码即门禁）、
`scripts/record_rag_vectors.py`（用真实 embedding 重录向量快照）。报告自动生成于
`docs/competition/评测报告.md`。README「质量」段补充评测说明与复现命令。

**确定性关键**：真实 LLM/Embedding 仅在录制冻结快照时调用，平时评测跑快照，故任何人
clone 后无需密钥/网络即可复现同一组数字。

## 接口与迁移

无接口、无迁移、无新增依赖、无运行时代码改动（纯 `tests/` + `scripts/` + 文档）。
另把 `docker-compose.server.yml`（服务器 .222 部署 override，无密钥）纳入跟踪。

## 验证

- `pytest tests/eval -q` → **4 passed**；全量离线 `pytest tests`（忽略 status/integration）→ **292 passed**。
- `python scripts/run_eval.py` 退出码 0、报告生成正常。
- 已合并 main 并 push origin（`d8b09fb`）；CI backend job 跑 `pytest tests` 自动纳入评测门禁。
- **服务器 .222 现状核对**：后端 `api/app`(208) + 前端 `ui`(112) 源码与 main **逐文件零差异**
  （行尾归一后），线上 `alembic current=d1e2f3a4b5c6 head`、`/api/status=200`、`/api/briefings/latest=401`，
  **运行时已是最新**。按用户决定**保持现状不重新部署**：本次推送是测试/文档/部署配置、零运行时影响，
  服务器只用于产品体验；评测复现由仓库侧 clone 执行（评委不需在 .222 上跑）。

## 未完成 / 候选增强

- 当前各项指标均为满分（语料清晰、模型够强，诚实结果）。如需"区分度"，可加更难干扰样本
  让部分指标 <1 但仍过阈值——属展示取向，未做。
- 可扩：截止抽取录制**真实模型输出快照**（现 ⑤ 离线评测的是纪律决策层；端到端走 `--live`）；
  匹配/检索数据集扩规模；把 `--live` 端到端纳入一个可选 CI job（需 key secret）。

## 风险

- RAG 向量快照与具体 embedding 模型/版本绑定；换模型需 `record_rag_vectors.py` 重录并复核阈值。
- 阈值是"低于当前观测值"的回归门禁，扩数据集后需同步校准，避免误红/误绿。

## 下一步

1. 无强制后续。若要服务器侧也能跑评测复现，再把最新 main 部署到 .222（`up -d --build`）。
