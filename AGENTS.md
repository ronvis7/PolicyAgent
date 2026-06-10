# PolicyManus Agent 协作协议

本文件是所有开发者和编码 Agent 的统一入口。开始任何任务前必须阅读。

## 项目目标

PolicyManus 是基于 GoodManus 二次开发的企业政策咨询 Agent。当前冲刺只保证以下主链路：

登录与租户切换 -> 创建知识库 -> 上传政策文件 -> RAG 检索 -> 带引用回答 -> 生成政策咨询报告 -> Docker 部署。

政策爬取只实现一个可演示来源。优秀案例第一版作为带类型和标签的知识材料使用。不在本期引入知识图谱、复杂 Agent 市场或大规模工作流编排。

## 开工必读

按以下顺序读取，避免一次加载无关内容：

1. `.agents/PRODUCT.md`
2. `.agents/STATUS.md`
3. 与任务相关时再读 `.agents/ARCHITECTURE.md`
4. 修改接口时读 `.agents/API_CONTRACTS.md`
5. 修改数据库或租户逻辑时读 `.agents/DATA_MODEL.md`
6. 修改部署时读 `.agents/RUNBOOK.md`
7. 阅读与任务相关的 `.agents/decisions/`
8. 阅读当前任务对应的 `.agents/handoffs/`

## 开工协议

1. 运行 `git status --short --branch`，不得覆盖其他人未提交的修改。
2. 确认当前 Issue、负责人、任务边界和验收标准。
3. 从最新 `develop` 创建功能分支，命名为 `feat/<topic>` 或 `fix/<topic>`。
4. 检查是否有人正在修改相同的数据表、公共接口或核心配置。
5. 先更新接口契约或数据模型约定，再开始跨前后端实现。
6. 保持改动聚焦，一个 PR 只解决一个 Issue。

## 完工协议

1. 运行与改动相关的测试、Lint、构建或 Compose 校验。
2. 更新被本次改动影响的共享记忆，不记录无关过程。
3. 在 `.agents/handoffs/` 新建交接文件，或更新本任务已有交接文件。
4. PR 描述必须包含：完成内容、接口/迁移变化、验证结果、剩余风险。
5. 不直接提交到 `main`；公共模型、迁移和 API 契约必须由另一人 Review。

## 记忆写入规则

- 稳定产品边界写入 `PRODUCT.md`。
- 稳定架构事实写入 `ARCHITECTURE.md`。
- 已实现的接口契约写入 `API_CONTRACTS.md`。
- 已确认的数据结构和隔离规则写入 `DATA_MODEL.md`。
- 当前进度、阻塞和下一步写入 `STATUS.md`。
- 不容易撤销的技术决策写入 `decisions/`。
- 临时上下文、未完成工作和具体续接步骤写入 `handoffs/`。
- GitHub Issue 是任务进度的事实来源；共享记忆不替代 Issue。
- 不写入密码、Token、私钥、真实客户数据或大段运行日志。
- 删除过时信息，不追加互相矛盾的历史叙述。

## 工程约束

- 所有租户业务数据必须带 `tenant_id`，后端是最终权限边界。
- Repository 查询不得依赖前端过滤实现租户隔离。
- 路由层保持轻量，业务流程放 application service，持久化放 repository。
- 前端请求统一经过 `ui/src/lib/api`，组件不得自行拼接后端地址。
- RAG、爬取和报告生成以可替换服务或 Agent 工具接入，不硬编码进页面。
- 数据库变更必须使用 Alembic，并提供升级路径。
- 优先复用现有 FastAPI、Next.js、PostgreSQL、Redis、COS 和 Sandbox 架构。
- Yuxi 是设计参考；复制其代码时必须确认许可证、依赖和当前架构适配性。

