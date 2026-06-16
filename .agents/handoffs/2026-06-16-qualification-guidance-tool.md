# 资质能力③ 材料/流程指引 Agent 工具（A2）

更新时间：2026-06-16
分支：`feat/qualification-guidance-tool`（PR 待合并）

## 背景

⑥ 资质主线 A0（档案结构化字段）+ A1（能力② 差距分析）已合 main（PR #22）。A2 是
能力③ 「材料/流程指引」：把资质目录与差距分析接入**聊天 Agent**，使其能复用聊天链路 +
`KnowledgeBaseTool` 取政策原文，生成"材料清单 + 申报流程指引"，并把差距分析里
`manual_review` 的软条件交 Agent 结合原文深化（混合引擎的"软"半边）。

## 交付：新增 Agent 工具 `QualificationTool`

`domain/services/tools/qualification.py`，`name="qualification"`，3 个工具函数：

- `qualification_list` —— 按当前租户档案返回可申报/接近候选（带 `key`/名称/是否可申报/缺前置），
  供 Agent 定位用户提到的资质。无档案返回成功但引导先完善档案。
- `qualification_gap(key)` —— 条件差距分析：逐条 达标✓/不达标✗/待确认?（缺字段判待确认，
  绝不误报不达标）+ 缺失前置 + `manual_review` 软条件；强制带 `disclaimer` + `last_reviewed`。
- `qualification_detail(key)` —— 核心条件/材料/时间/政策依据/价值；同样强制风险纪律字段（不需租户）。

**分层**：工具内核全走 **domain 纯函数**（`match_qualifications` / `analyze_gap`）+ uow 读档案，
**不**依赖 application 的 `QualificationService` 与 infrastructure，目录（catalog）由构造链注入。
租户范围由会话懒加载（同 `KnowledgeBaseTool`），多租户隔离。

**工具说明（prompt 语义）**：明确要求 Agent 对"不达标/待确认/需人工确认"项再调
`knowledge_base_search` 取该资质对应政策原文交叉核对后再下结论，并连同免责声明告知用户。

## 装配链（interfaces → domain，方向干净）

`_build_agent_service`（service_dependencies）加载 `load_qualification_catalog()`
→ `AgentService`（新增 `qualification_catalog` 参数）
→ `AgentTaskRunner`（新增参数）
→ `PlannerReActFlow`（新增参数，构造 `QualificationTool` 注册进 planner+react 共享工具集）。

## SSE 专属卡片

- 后端：`event.py` 新增 `QualificationToolContent`（kind/title/summary/lines/disclaimer/last_reviewed）
  并入 `ToolContent` 联合；`agent_task_runner._handle_tool_event` 加 `tool_name=="qualification"`
  分支，把 `function_result.data`（`QualificationToolData`）映射成卡片内容。
- 前端：`tool-use/utils.ts` 加 `qualification` ToolKind + `getToolKind`/`getFriendlyToolLabel` 分流；
  新 `tool-use/qualification-tool.tsx`（`Award` 徽章）并注册进 `tool-use/index.tsx`；
  `tool-preview-panel.tsx` 加 `QualificationPreview`（标题/总览/逐条要点/琥珀色免责声明带末次核对日期）
  及三处 `Record<ToolKind>` 穷举映射。

## 验证

- 后端单测：`test_qualification_tool.py` 新增 8（清单/无档案引导/缺租户失败/gap 三态+风险字段/
  缺字段判待确认不误报/未知 key 失败/detail 材料+依据/detail 未知 key）；**全量 142 passed**
  （1 error 为既有需真库的 `test_get_status`，与本次无关）；改动模块 import OK。
- 前端 `tsc --noEmit` 干净；eslint 改动文件 0 error（2 warning 为既有 `ToolPreviewPanel`
  头部 `ToolIcon` 写法，非本次）；`next build` 通过。
- `alembic head` 仍 `f7a8b9c0d1e2`（零迁移）。
- **真机走查待做**：起开发栈连 .222，聊天里问"我能申报哪些资质 / 高企还差什么 / 申报要哪些材料"，
  验证 Agent 调 qualification_* 工具 + 结合 knowledge_base_search 出指引、卡片渲染、免责声明在位。

## 后续

- 资质目录其余 24 条逐条**校对数值**后补 `structured_conditions`（当前仅高企已结构化，差距分析才更全）。
- 公开库语义检索接入 Agent（`KnowledgeBaseTool` 纳入 is_public 库）——配合本工具可让 Agent 直接
  取公开政策原文，是 A2 体验的天然增强（属③范畴的后续小分支）。
- 报告生成流水线。
