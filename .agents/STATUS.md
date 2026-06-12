# 当前状态

最后更新：2026-06-12

## 仓库状态

- 主仓库：`policy_manus`，当前分支 `main`，工作区干净。
- `main` 已合入 R1+R2+R3（PR #1/#2/#3）。

## 已完成

> 细节以 `git log` 为准，本节只记里程碑。

- 多租户后端闭环：tenants/users/memberships + JWT + 租户切换；sessions/files/平台配置隔离。
- 前端认证闭环：登录/注册、Token 存储与 401 刷新、路由守卫、租户切换器、平台模型 API 配置页。
- Docker Compose 全量构建启动验证（`policy-*` 资源，库名 `policy_manus`）；Alembic 读统一运行时配置。
- `.agents/` 协作记忆体系。
- **RAG R1**：三表 + pgvector 向量存储 + 知识库管理 REST 端点。
- **RAG R2**：入库流水线（解析→分块→Embedding→落库）。
- **RAG R3**：`KnowledgeBaseTool` 接入 Agent，自主检索 + 带来源（文件名/页码/相似度）作答，引用经 SSE 渲染来源卡片。
- **RAG R4**：知识库管理前端页（`/knowledge`：建库/上传/FileStatus 进度轮询/删除，独立非聊天模块）。已真机联调通过（建库→上传→indexed、级联删除、页面 SSR 均 OK），并修复删除端点 `Response[None]` 致 500 的后端 bug（`feat/rag-r4-knowledge-ui` 分支）。

## 未完成

- 会话级 KB scope 选择器（Session 加列 + 迁移 + 绑定端点 + 前端选择器）。
- 可选：聊天内问政策验证引用、单文件删除端点、上传前端校验、app 日志输出到 stdout。
- 前端认证闭环真机联调；成员邀请与组织成员管理；多租户自动化测试。
- 政策爬取；报告生成流水线；GitHub Actions 与分支保护。

## 当前最高优先级

1. R4 知识库管理前端页，打通「上传政策文件→索引→检索引用」完整闭环。
2. 多租户端到端真机联调与自动化测试。
3. 报告生成流水线。

## 已知风险

- 后端多租户测试覆盖不足，跨租户读取风险未系统验证。
- `.env`（腾讯 COS、`EMBED_API_KEY`）与 `api/config.yaml` 是 Docker 启动前置；含真实机密，保持 gitignored。
- 检索默认全库，租户库多时为顺序循环，规模大需批量/并发或会话级 scope 收窄。
- 十天范围紧，新增基础设施须直接服务主链路。

## 更新规则

只记录最新事实。任务细节放 GitHub Issue，临时交接放 `handoffs/`，架构原因放 `decisions/`。
