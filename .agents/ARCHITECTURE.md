# 架构记忆

## 当前技术栈

- 前端：Next.js 16、React 19、TypeScript。
- API：FastAPI、Pydantic、SQLAlchemy Async、Alembic。
- 业务数据库：PostgreSQL。
- 缓存和消息：Redis。
- 对象存储：腾讯云 COS。
- 工具执行：Docker Sandbox。
- 网关：Nginx。
- 部署入口：根目录 `docker-compose.yml`。

## 代码边界

- `api/app/interfaces`：HTTP 路由、请求响应 Schema、认证依赖。
- `api/app/application`：用例编排和应用服务。
- `api/app/domain`：领域模型、Repository 协议、Agent 与工具抽象。
- `api/app/infrastructure`：SQLAlchemy、Redis、COS、Docker、模型服务等实现。
- `api/alembic`：数据库迁移。
- `ui/src/lib/api`：前端 API 客户端和类型。
- `ui/src/components`：交互组件。
- `sandbox`：浏览器、Shell 和文件工具运行环境。

## 多租户链路

访问令牌携带 `user_id`、`tenant_id` 和租户角色。FastAPI 认证依赖生成 `CurrentUser`，路由把租户上下文传入应用服务，Repository 使用 `tenant_id` 过滤数据。

当前已有：

- `tenants`、`users`、`memberships`。
- 注册、登录、刷新、退出和租户切换后端接口。
- sessions 和 files 的租户字段及查询隔离。
- 平台配置的 platform admin 保护。

前端认证链路尚未完成。

## RAG 目标链路

```text
文件上传
  -> COS 原文件
  -> 文档解析
  -> 文本规范化
  -> 分块
  -> Embedding
  -> 向量写入
  -> 检索
  -> Agent 工具
  -> 带引用回答
```

十天版本优先使用 PostgreSQL + pgvector，避免同时引入 Milvus、etcd 和 MinIO。向量存储必须通过接口封装，为后续替换保留边界。

## 长任务

文档解析、Embedding、爬取和报告生成都应有任务记录及状态。十天版本可先复用 Redis 和现有后台执行方式，不在本期整体移植 Yuxi 的 ARQ/LangGraph 运行体系。

## Yuxi 参考边界

适合参考：

- KnowledgeBase、KnowledgeFile、KnowledgeChunk 模型。
- 内容哈希去重和文档状态机。
- 分块策略接口。
- `list_kbs`、`query_kb`、`open_kb_document` 工具语义。
- 检索引用、评估和权限设计。

不直接移植：

- Vue 前端。
- LangGraph Agent Middleware。
- Milvus/etcd/MinIO/Neo4j 整套基础设施。
- 与 Yuxi 用户模型强耦合的 Repository 和路由。

