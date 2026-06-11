# RAG R1：数据模型与向量存储

Issue：待创建
分支：`feat/rag-r1-datamodel`（从 `main` @ `e250705` 切出）
负责人：项目组
更新时间：2026-06-11

## 目标

落地 RAG 第一刀（R1）：建立知识库 / 文件 / 切片的领域模型、ORM 模型与
pgvector 向量存储，使后续的解析、Embedding、检索可以在稳定的数据契约上开发。
验收：迁移可在 `policy-postgres` 上正常执行，三张表与向量索引建成，模型注册到
`models/__init__.py`，应用启动不报错。

## 背景：已落地的前置改动（均已提交在 `main` @ `e250705`）

> 这些不是本分支的工作，是接手前的事实。`main` 工作区干净，无遗漏未提交项。

- **修复注册/登录闭环三个后端 bug**（注册 200 但登录 401 / 数据未持久化）：
  1. `model_dump(mode="json")` 把 datetime 序列化成字符串，asyncpg 绑定
     TIMESTAMP 列报 DataError → 改为 `model_dump()`（user/tenant/membership/file 四个模型）。
  2. `autoflush=False` 且模型间无 `relationship()`，同一事务内 membership 先于
     user/tenant 插入导致外键违例 → UoW 新增 `flush()`，`auth_service.register()`
     在写 membership 前显式 flush。
  3. `db_uow.__aexit__` 吞掉提交异常，把失败当 200 返回 → 改为 `exc_type is None`
     时重新抛出。
- **`api/run.sh` CRLF 导致容器启动报 `exec ./run.sh: no such file or directory`**：
  转为 LF，并新增 `.gitattributes`（`*.sh text eol=lf`）锁定。
- **前端注册页**新增「确认密码」输入与两次一致性校验。
- **`docker-compose.yml`**：`policy-postgres` 镜像由 `postgres:16-alpine` 换为
  `pgvector/pgvector:pg16`（同 PG16 大版本，数据目录兼容）。

以上注册/登录修复已在 `http://localhost:8888/api` 端到端验证通过
（注册 200 / 正确登录 200 / 错误密码 401 / 重复注册 409，DB 中 user+membership+tenant 均持久化）。

## 关键决策（详见 `.agents/decisions/001-use-pgvector-for-mvp.md` 与记忆 `rag-decisions.md`）

- **向量存储**：复用现有 Postgres 的 pgvector 扩展，不引入 Milvus 等新组件；
  向量表带 `tenant_id`，延续行级租户隔离。
- **Embedding**：先用 API（DeepSeek 无 embedding 端点，需独立 `embed_config`），
  打通后再换本地开源模型。
- **向量维度 = 1024**：对 text-embedding-v3 与未来本地 bge-m3 都前向兼容。
- **Yuxi 仅借两处模式**：可插拔 `KnowledgeBase` ABC + 工厂；`FileStatus` 状态机
  （uploaded→parsing→parsed→indexing→indexed→error_parsing/error_indexing）。整体不移植。

## 接口与迁移

本分支尚未产生任何接口或迁移变更——见「未完成」。

## 验证

- `pgvector/pgvector:pg16` 镜像已拉取，`policy-postgres` 重建后 healthy。
- 镜像切换（musl→glibc）后旧数据完好：`users=3, tenants=3`。
- `CREATE EXTENSION vector` 成功，`extversion = 0.8.2`。

## 未完成（R1 剩余，按序执行）

1. `api/config.yaml` 与 `core/config` Settings 新增 `embed_config`
   （base_url / api_key / model_name / dimension=1024）。
2. 领域模型：`KnowledgeBase`、`KnowledgeFile`（含状态机）、`DocumentChunk`。
3. infra ORM 模型：含 `vector(1024)` 列与 `tenant_id`，注册进
   `api/app/infrastructure/models/__init__.py`。
4. Alembic 手写迁移：`down_revision="e5f6a7b8c9d0"`，包含
   `CREATE EXTENSION IF NOT EXISTS vector` + 三张表 + 向量索引（ivfflat/hnsw）。
5. Repository + UoW 接线（参照现有 repo/UoW 模式，含 `tenant_id` 过滤）。

后续刀：R2 入库（COS 上传→PyMuPDF 解析→分块→Embedding→落库）、
R3 检索 + 引用回答、R4 知识库前端页。

## 风险

- **`.env` 含真实腾讯 COS 凭据**（live secrets）。绝不可提交、打印、写入仓库；
  `.env` 必须保持 gitignore。新增 `embed_config` 的 api_key 同样走 `.env`，不入库。
- 迁移须手写（项目 Alembic 不用 autogenerate），`down_revision` 必须接当前 head
  `e5f6a7b8c9d0`，否则迁移链断裂。
- pgvector 索引（ivfflat）需要在有数据后或用合适 `lists` 参数建，空表建索引需注意。
- **提交纪律**：本分支编码完成后，需人工确认无误再提交；不要在 `main` 上直接改。

## 下一步

1. 在本分支 `feat/rag-r1-datamodel` 上，从「未完成」第 1 步开始：
   给 `config.yaml` + Settings 加 `embed_config`（维度 1024，api_key 占位走 `.env`）。
2. 然后建三个领域模型与对应 ORM，注册到 `models/__init__.py`。
3. 写迁移并在 `policy-postgres` 上 `alembic upgrade head` 验证建表成功。
4. R1 验收通过后人工确认 → 提交 → 合回 `main` → 再开 R2 分支。
