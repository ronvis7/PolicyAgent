# RAG R4：知识库管理前端页

PR：[#4](https://github.com/ronvis7/policy_manus/pull/4)（已开，待审/合）
分支：`feat/rag-r4-knowledge-ui`（从含 R1+R2+R3 的 `main` 切出，即 `388b49b`；提交 `d4c7ff1`）
状态：真机联调通过，已推送开 PR；待 review + merge
负责人：项目组
更新时间：2026-06-12

## 目标

按 ADR-002「知识库管理为独立非聊天模块」，在前端 `ui/` 落地知识库管理页：建库、
上传文件、查看文件处理进度（`FileStatus` 状态机）、删除库。打通「上传政策文件 →
后台解析入库 → 列表可见可检索」的人机闭环（检索本身已在 R3 的 Agent 工具中可用）。

## 背景：已落地的前置

- **R1/R2/R3 已在 `main`**：三表 + pgvector + 入库流水线 + 知识库管理 REST 端点
  （PR #1），检索 Agent 工具（PR #2）。
- **后端知识库端点早已实现**（`api/app/interfaces/endpoints/knowledge_routes.py`），
  本刀**纯前端**，未改后端。

## 关键决策

- **路由**：`/knowledge`（库列表）、`/knowledge/[id]`（库详情：文件列表 + 上传）。
  挂在已登录 `AppShell` 内，侧边栏「新建任务」下方新增「知识库」入口。
- **实际端点为 `/{kb_id}/files`**（非旧契约里的 `/documents`）；检索不走 REST，而是
  R3 的 Agent 工具——已据此修正 `.agents/API_CONTRACTS.md`。
- **异步入库进度靠前端轮询**：上传后文件状态 `uploaded→…→indexed` 由后台 BackgroundTask
  推进；`useKnowledgeFiles` 在存在处理中文件时每 3s 轮询列表，全部进入终态后自动停。
- **删除二次确认**：删库级联清文件与向量，故用确认弹窗（`DeleteKbDialog`）。
- **租户隔离沿用既有机制**：所有请求带 `Authorization`，租户上下文来自令牌，前端不传租户参数。

## 接口与改动（均在 `ui/src/`）

- 新增 API 层 `lib/api/knowledge.ts`：`knowledgeApi`（list/create/get/delete 库、
  listFiles、uploadFile）+ 类型 `KnowledgeBase` / `KnowledgeFile` / `FileStatus` +
  `isFileProcessing` / `isFileFailed`；`lib/api/index.ts` 统一导出。
- 新增 hooks：`hooks/use-knowledge-bases.ts`（列表 + 建/删，乐观本地更新）、
  `hooks/use-knowledge-files.ts`（详情 + 文件列表 + 上传 + 处理中轮询）。
- 新增页面：`app/knowledge/page.tsx`（卡片网格 + 空态 + 建/删）、
  `app/knowledge/[id]/page.tsx`（拖拽/点击上传 + 文件列表 + 状态徽标）。
- 新增组件 `components/knowledge/`：`create-kb-dialog`、`delete-kb-dialog`、
  `file-status-badge`（状态→中文文案/Badge 变体，处理中带 spinner）。
- 改 `components/left-panel.tsx`：加「知识库」侧边栏入口。
- 无新增第三方依赖。

## 验证

- `npx tsc --noEmit` 零错误；`npx eslint` 对新增文件零告警。
- **真机端到端联调通过**（Docker 全栈 nginx→api→pg/redis + 真实腾讯 COS + 真实
  DashScope embedding）：
  - 注册/登录、建库、列表、详情、列文件 ✅
  - 上传 `.md` → 后台 `uploaded→parsing→parsed→indexing→indexed`，`chunk_count=1` ✅
    （真实 COS 落对象 + 真实 embedding 向量化）
  - 删除空库 ✅；删除含 1 个 indexed 文件的库 ✅，DB 校验 `document_chunks`/
    `knowledge_files` 0 孤儿（FK ON DELETE CASCADE 生效）
  - 前端 `/knowledge`、`/knowledge/[id]` 经 nginx SSR 返回 200 ✅
- **联调中修复 1 个后端 bug**（见下）。

## 联调中修复的后端 bug（R1 遗留）

- **删除知识库 500（ResponseValidationError）**：`delete_knowledge_base` 路由
  `response_model=Response[None]`，但 `Response.success` 在无数据时把 `data` 归一为 `{}`，
  与 `Response[None]`「data 必须为 None」冲突，FastAPI 响应校验抛 500。改为
  `response_model=Response`（与 success 的空字典语义一致）。`Response[None]` 全仓仅此一处。
- **环境配置**（非代码，已在本机 `.env` 修正，**不入库**）：`COS_BUCKET` 原为占位
  `your-bucket-name-xxxxxxxx`、`COS_REGION` 与实际桶地域不符；上传依赖真实桶。部署/联调
  前必须在 `.env` 填真实 `COS_BUCKET` + 对应 `COS_REGION`。

## 未完成 / 下一步

- **会话级 KB scope 选择器**（Session 加列 + 迁移 + 绑定端点 + 前端选择器）。
- 可选：单文件删除（后端暂无该端点）、上传类型/大小前端校验、分页、聊天内问政策验证引用。
- R5/报告生成流水线。
- 旁注：app 级日志（`logger.error/warning`）未输出到容器 stdout，排障只能见 sqlalchemy/
  uvicorn 日志；建议后续补 logging 配置，便于线上排查。

## 风险

- **轮询而非推送**：库内文件多或并发上传多时，3s 轮询有冗余请求；后续可换 SSE/WS 或
  按需收敛间隔。
- **后端无单文件删除端点**：当前只能删整库，单文件管理待后端补。
- **提交纪律**：走 `feat/rag-r4-knowledge-ui` 分支 + PR，勿直推 `main`。
