# RAG R3：检索 + 引用回答（KnowledgeBaseTool 接入 Agent）

Issue：待创建
分支：`feat/rag-r3-retrieval`（从含 R1+R2 的本地 `main` 切出，即 `57b33ee`）
负责人：项目组
更新时间：2026-06-12

## 目标

在 R2 入库流水线之上，按 ADR-002 的 agentic RAG 形态，把「政策知识库检索」作为
Agent 的一个工具接入现有聊天窗口：用户问政策 → Agent 自主调用检索工具 → 基于命中
切片作答并标注来源（文件名 + 页码）。验收：工具在真实 embedding + pgvector 下跑通
检索并产出带引用的结果，引用经事件流可在前端渲染为来源卡片。

## 背景：已落地的前置（接手前事实）

- **R1/R2 已合入 `main`**（PR #1，`57b33ee`）：三表 + pgvector + 入库流水线（解析→
  分块→Embedding→落库），知识库管理 REST 端点。详见 `2026-06-11-rag-r1-datamodel.md`、
  `2026-06-12-rag-r2-ingest.md`。
- **ADR-002 已定**：检索作 Agent 工具、知识库管理独立模块、单聊天窗口。
- **现有 Agent 架构**：`PlannerReActFlow` 用一份共享 `tools` 列表创建 planner/react 两个
  Agent；工具继承 `BaseTool`、用 `@tool` 声明 OpenAI schema；工具结果 `ToolResult` 经
  `ToolEvent.tool_content` 走 SSE，前端 `tool-preview-panel` 渲染。

## 关键决策

- **检索范围（scope）：默认搜全部租户库**（本刀范围决策）。`knowledge_base_search`
  默认检索当前会话租户下的**全部**知识库并跨库合并排序，`knowledge_base_id` 为可选
  收窄参数。**不改 Session 表、不加迁移**。ADR-002 提到的「会话级 KB 绑定选择器」
  留作后续增强（需 Session 加列 + 迁移 + 前端选择器）。
- **租户隔离边界来自会话**：工具构造时拿 `session_id`，首次调用懒加载会话的
  `tenant_id` 作为检索边界（呼应 `AgentTaskRunner._get_session_scope` 的既有模式），
  确保多租户隔离。
- **向量仍不出仓库**：检索经 `DocumentChunkRepository.search_similar`，工具不碰
  pgvector SQL（呼应 ADR-001）。
- **引用 = 结构化事件内容**：新增 `KnowledgeToolContent`（citations 列表），由
  `AgentTaskRunner._handle_tool_event` 在 `knowledge` 工具调用后注入，经 SSE 的
  `tool_content→content` 映射透传到前端渲染来源卡片（文件名/页码/相似度/切片节选）。
- **提示词引导**：`REACT_SYSTEM_PROMPT` 加「知识库优先 + 标注来源」，让 Agent 对政策类
  问题优先检索内部库、外部 `search_web` 兜底。

## 接口与改动

- **无新增迁移**（复用 R1 三表）。**无新增 REST 端点**（检索走 Agent 工具，非独立 API）。
- **新增**：
  - `domain/models/knowledge_search.py`：`KnowledgeCitation` / `KnowledgeSearchResults`。
  - `domain/services/tools/knowledge.py`：`KnowledgeBaseTool`（`knowledge_base_search`）。
  - `domain/models/event.py`：`KnowledgeToolContent` 并入 `ToolContent` 联合。
  - 前端 `ui/`：`tool-use/knowledge-tool.tsx`（徽标）、`tool-preview-panel` 的
    `KnowledgePreview`（来源卡片）、`tool-use/utils.ts` 识别 `knowledge` 类型与文案。
- **接线**：`embedding` 依赖经 `service_dependencies(get_agent_service)` → `AgentService`
  → `AgentTaskRunner` → `PlannerReActFlow` 贯通，并在 flow 的共享 `tools` 列表注册
  `KnowledgeBaseTool`（planner/react 共用）。
- **依赖**：无新增第三方依赖（复用 `OpenAIEmbedding`）。

## 验证

- **单元测试**（`tests/app/domain/services/tools/test_knowledge_tool.py`，fake repo+embedding，
  5/5 通过）：跨库合并按相似度全局倒序并截断 top_k、单库收窄、租户缺失拒绝、空库空结果、
  空查询拒绝；并断言 `search_similar` 收到正确租户隔离条件。
- **端到端冒烟**（重建镜像后在 `policy-api` 容器内，真实 DashScope embedding + 真实
  policy-postgres pgvector）：注入 R2 验证数据所属租户，查询「研发费用加计扣除 比例」→
  跨两个「R2验证库」合并命中 3 条切片，每条带来源 `r2.pdf`+页码+相似度（top1 ≈ 0.51），
  `success=True`。检索/合并/文件名回查/引用构建全链路真实跑通。
- 后端全链路 import + `py_compile` 通过；SSE `ToolSSEEvent.from_event` 实测把
  `KnowledgeToolContent` 透传为 `content.citations`。前端 `tsc --noEmit` 零错误。

## 未完成 / 下一步

- **会话级 KB scope 选择器**：Session 增 `knowledge_base_id` + 迁移 + 绑定端点 + 前端
  选择器，让用户把会话限定到指定库（当前默认全库已可用）。
- **R4：知识库管理前端页**（建库/上传/查看 `FileStatus` 进度，独立非聊天模块）。
- **可选**：内联引用编号（答案正文 `[1][2]` 对应来源卡片）；严格知识库模式开关（ADR-002
  列为 YAGNI，待产品确有强约束再做）。

## 风险

- **`.env` 含真实机密**（腾讯 COS、`EMBED_API_KEY`）：绝不提交/打印/入库；保持 gitignored。
- **检索默认全库**：租户库较多时逐库检索为顺序循环，库数量大时需改批量/并发或上
  会话级 scope 收窄（已在「下一步」）。
- **提交纪律**：走 `feat/rag-r3-retrieval` 分支 + PR 合入，勿直接 push 本地 `main`。
