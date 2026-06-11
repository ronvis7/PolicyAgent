# RAG R2：入库流水线（解析→分块→Embedding→落库）

Issue：待创建
分支：`feat/rag-r2-ingest`（从含 R1 的本地 `main` 切出，即 `a8b556f`）
负责人：项目组
更新时间：2026-06-12

## 目标

在 R1 数据契约（知识库/知识库文件/文档切片三表 + pgvector）之上，打通知识库
文件的入库全链路：上传原始文件 → 落 COS → 解析 → 分块 → Embedding → 写入
`document_chunks`，并暴露知识库管理 + 文件上传/列表的 REST 接口。验收：上传文件
后经后台流水线沿 `FileStatus` 状态机推进到 `indexed`，切片带向量可被检索。

## 背景：已落地的前置（接手前事实）

- **R1 已合入本地 `main`**（`d46c191`）：三表 + ORM + pgvector 迁移 `f6a7b8c9d0e1`
  （DB 已 `upgrade head`）+ 三仓库接入 UoW。详见 `2026-06-11-rag-r1-datamodel.md`。
- **ADR-002 已定**（`a8b556f`）：RAG 采用 agentic 形态——检索作 Agent 工具、
  知识库管理独立模块、不另起并列聊天窗口。见 `.agents/decisions/002-rag-as-agent-tool.md`。
- **Embedding API 已配通**：`.env` 的 `EMBED_API_KEY` 已填真实值，冒烟测试返回
  `dim=1024`（DashScope text-embedding-v3，OpenAI 兼容端点）。
- **修复既有 redis 崩溃**：`policy-redis` 无密码但 `.env` 的 `REDIS_PASSWORD` 被设值
  导致应用 AUTH 失败崩溃循环；已清空 `.env` 的 `REDIS_PASSWORD`（与项目 passwordless
  设计一致，`.env` gitignored 不入库）。现 `policy-api` healthy。

## 关键决策

- **异步入库用 FastAPI `BackgroundTasks`**，不用 `redis_stream_task`（后者是为 Agent
  交互式流式执行+沙箱设计的，入库场景过重）。`FileStatus` 状态机 + 文件列表轮询
  即可呈现进度。多实例水平扩展时再换 Redis 消费者。
- **向量不入领域模型**：`DocumentChunk` 不含 embedding，向量读写封装在
  `DocumentChunkRepository`（呼应 ADR-001）。
- **解析器**：PyMuPDF，PDF 按页提取（页码进 `chunk_metadata` 供 R3 引用），txt/md
  单页，utf-8→gbk 回退。docx 暂不支持（YAGNI）。
- **分块**：纯逻辑 `domain/services/chunker.py`，逐页定窗+重叠（默认 1000 字 / 150 重叠），
  保留页码。
- **Embedding 批量上限 10**（DashScope text-embedding-v3 兼容端点单批限制），自动分批 +
  维度守卫（返回维度≠配置则报错）。

## 接口与迁移

- **无新增迁移**（复用 R1 三表）。
- **新增端点**（`/api`，均需登录，租户隔离）：
  - `POST /knowledge-bases`、`GET /knowledge-bases`、`GET /knowledge-bases/{id}`、
    `DELETE /knowledge-bases/{id}`
  - `POST /knowledge-bases/{id}/files`（上传，后台触发入库）、
    `GET /knowledge-bases/{id}/files`（列表+状态）
- **新增模块**：`EmbeddingProvider`/`DocumentParser` 接口、`OpenAIEmbedding`、
  `PyMuPDFParser`、`chunker`、`KnowledgeService`、`knowledge_routes`、
  `schemas/knowledge.py`；接入 `routes.py` 与 `service_dependencies.py`。
- **依赖**：新增 `pymupdf>=1.24.0`，已同步 `uv.lock`/`requirements.txt`。

## 验证

- 真实 Embedding API + policy-postgres 端到端脚本：PDF 按页解析、中文分块、真实
  向量化（1024 维）、落库、语义检索（查“研发费用加计扣除”命中对应切片 sim=0.85）全通过。
- `import app.main` 正常，6 个知识库路由注册到 `/api`。
- 线上容器 healthy；`/api/status`→200，`/api/knowledge-bases`（无 token）→401。

## 未完成 / 下一步

- **R3（检索 + 引用回答）**：按 ADR-002 实现 `KnowledgeBaseTool`
  （`knowledge_base_search` → `DocumentChunkRepository.search_similar`）挂进 `react` Agent，
  消息事件流渲染引用（用切片 `chunk_metadata` 的页码 + 文件名），会话级知识库 scope 选择器。
- **R4**：知识库管理前端页（独立非聊天模块）。
- **可选硬化**：BackgroundTasks 不抗进程重启——若上传后 API 重启，处于
  parsing/indexing 的文件会停在中间态。R3+ 可加“重新索引”入口或迁移到 Redis 消费者。

## 风险

- **`.env` 含真实机密**（腾讯 COS、`EMBED_API_KEY`）：绝不提交/打印/入库；`.env` 保持 gitignored。
- **远端 `main` 已分叉**：`origin/main` 有协作者的 `8baad27`（secure model API
  configuration），本地 `main` 含 RAG 提交但无 `8baad27`。RAG 工作走 feature 分支 + PR
  合入，勿直接 push 本地 `main`。
