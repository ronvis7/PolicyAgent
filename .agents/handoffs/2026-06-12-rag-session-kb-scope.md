# RAG：会话级知识库 scope 选择器

Issue：待创建
分支：`feat/rag-session-kb-scope`（从含 R1~R4 + CI 的 `main` 切出，即 `2aa74fa`）
负责人：项目组
更新时间：2026-06-12

## 目标

落地 R3/R4 反复点名的头号遗留：让用户把单个会话的政策检索范围**硬限定**到指定
知识库，或恢复「全部知识库」。补齐 ADR-002 提到的「会话级 KB 绑定选择器」。

## 关键决策

- **绑定语义＝硬限定**（与用户确认）：会话绑定某库后，`knowledge_base_search` 工具
  **忽略 Agent 自传的 `knowledge_base_id`**，检索只在绑定库内进行。未绑定时维持
  既有默认全库检索。优先级：会话绑定 > LLM 参数 > 全库。
- **删库自动解绑**：`sessions.knowledge_base_id` 外键 `ON DELETE SET NULL`，删除
  知识库时相关会话自动解绑回全库，避免悬挂引用（无需应用层兜底）。
- **工具顺着既有懒加载扩展**：`KnowledgeBaseTool` 原已懒加载 `session.tenant_id`
  作隔离边界；本刀把它泛化为 `_load_scope()`，一并缓存 `session.knowledge_base_id`，
  零额外查询。
- **选择器放聊天输入区**：挂在 `session-detail-view` 的 ChatInput 上方（而非塞进通用
  ChatInput，后者首页无会话也复用）。知识库列表首次展开下拉时按需加载。

## 接口与改动

### 后端
- **领域模型** `domain/models/session.py`：`Session` 加 `knowledge_base_id: Optional[str]`。
- **PO** `infrastructure/models/session.py`：加列 `knowledge_base_id`，FK→`knowledge_bases.id`
  `ON DELETE SET NULL`，带索引。`from_domain/to_domain` 走 `model_dump` 自动带，未改。
- **迁移** `alembic/versions/a1b2c3d4e5f6_*.py`（down_revision=`f6a7b8c9d0e1`）：add_column +
  index + FK。
- **仓库** `session_repository.py` 协议 + `db_session_repository.py` 实现：新增
  `update_knowledge_base_id(session_id, kb_id)`。
- **服务** `session_service.py`：`bind_knowledge_base(session_id, tenant_id, kb_id)`——
  校验会话归属 + （非 None 时）校验 kb 归属同租户，再写绑定。
- **端点** `session_routes.py`：`POST /sessions/{id}/knowledge-base`，body
  `{ knowledge_base_id: str|null }`；`GET /sessions/{id}` 响应加 `knowledge_base_id`。
- **schema** `schemas/session.py`：`BindKnowledgeBaseRequest` + `GetSessionResponse` 加字段。
- **工具** `tools/knowledge.py`：`_get_tenant_id` → `_load_scope`（缓存 tenant + bound kb），
  检索前若有绑定则覆盖 `knowledge_base_id`。

### 前端（`ui/src/`）
- `lib/api/session.ts`：`bindKnowledgeBase(sessionId, kbId|null)`；`types.ts` 的
  `SessionDetail` 加 `knowledge_base_id?: string|null`。
- 新增 `components/knowledge-scope-selector.tsx`：DropdownMenu 选择器（全部知识库 +
  各库），乐观更新 + 失败回滚 + toast，列表按需加载。
- `components/session-detail-view.tsx`：输入区上方挂选择器，`value=session.knowledge_base_id`，
  运行中禁用。

## 验证

- **后端单测**（`tests/app/domain/services/tools/test_knowledge_tool.py`，7/7 通过）：
  原 5 条 + 新增 2 条——会话绑定时默认硬限定到绑定库、绑定覆盖 LLM 显式传入的另一库。
  Fake session repo 改返回真正的 `Session` 域模型（带 tenant + 绑定）。
- **后端**：`compileall app core` 通过；`import app.main` 通过（端点/schema 接线 OK）。
- **前端**：`tsc --noEmit` 零错误；`npm run lint` 0 error（31 warning 均既有技术债）；
  `npm run build` 成功。
- **未做**：真机端到端联调（Docker 全栈 + 真实 embedding）。迁移仅离线编写，**未对真库
  跑过 `alembic upgrade head`**。

## 未完成 / 下一步

- **真机联调**：起栈跑 `alembic upgrade head` 验证迁移；建库→绑定→提问验证检索确实被
  限定到绑定库（可对比绑定前后命中来源所属库）；删库后验证会话自动解绑回全库。
- 可选：在来源卡片/输入区回显「当前检索范围」更显式；绑定库为空库时给用户提示。
- 仍待办（沿用既有 backlog）：报告生成流水线（R5）、政策爬取、多租户自动化测试、
  集成测试纳入门禁、app 日志输出 stdout、升回 3 条 react-hooks 规则。

## 风险

- **迁移未对真库执行**：合并前务必在联调环境 `alembic upgrade head` 验证，注意 FK
  目标表 `knowledge_bases` 须已存在（R1 迁移 `f6a7b8c9d0e1` 已建，本迁移依赖其后）。
- **硬限定的副作用**：绑定到一个**空库或无关库**时，检索将稳定返回空，用户可能误以为
  「知识库没内容」。属预期语义，但 UX 上后续可加范围提示。
- **提交纪律**：走 `feat/rag-session-kb-scope` 分支 + PR，勿直推 `main`。CI 门禁会自动跑。
