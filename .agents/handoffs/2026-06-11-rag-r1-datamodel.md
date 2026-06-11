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

- **迁移**：`f6a7b8c9d0e1_add_rag_tables.py`（`down_revision=e5f6a7b8c9d0`）。
  `CREATE EXTENSION IF NOT EXISTS vector` + 三表（knowledge_bases / knowledge_files /
  document_chunks）+ 向量列 `vector(1024)` + HNSW 余弦索引
  `ix_document_chunks_embedding_hnsw`（vector_cosine_ops）。
- **领域接口**：`KnowledgeBaseRepository` / `KnowledgeFileRepository` /
  `DocumentChunkRepository`（均带 `tenant_id` 过滤），已接入 `IUnitOfWork`
  与 `DBUnitOfWork`（`uow.knowledge_base / knowledge_file / document_chunk`）。
  向量读写封装在 `DocumentChunkRepository`（save/add_many/search_similar/
  delete_by_knowledge_file），应用服务不直接依赖 pgvector SQL（呼应 ADR-001）。
- **配置**：`AppConfig.embed_config`（base_url/model_name/dimension=1024，api_key 占位空）
  写在 `config.yaml`；机密 `api_key` 经 `Settings.embed_api_key`（`.env` 的 `EMBED_API_KEY`）注入，不入库。
- **依赖**：新增 `pgvector>=0.3.6`，`uv.lock` 与 `requirements.txt` 已同步。

## 验证

- `pgvector/pgvector:pg16` 镜像已拉取，`policy-postgres` 重建后 healthy。
- 镜像切换（musl→glibc）后旧数据完好：`users=3, tenants=3`。
- `CREATE EXTENSION vector` 成功，`extversion = 0.8.2`。

## 已完成（R1，全部落地并验证）

1. ✅ `config.yaml` + `core/config` Settings 新增 `embed_config`（dimension=1024，
   api_key 走 `.env` 不入库），`.env.example` 补 `EMBED_API_KEY`。
2. ✅ 领域模型：`KnowledgeBase`、`KnowledgeFile`（`FileStatus` 状态机）、`DocumentChunk`
   （向量不入领域模型，由仓库承载）。
3. ✅ infra ORM 模型：`vector(1024)` 列 + `tenant_id` 行级隔离，已注册进
   `infrastructure/models/__init__.py`。
4. ✅ Alembic 手写迁移 `f6a7b8c9d0e1`（接 head `e5f6a7b8c9d0`），向量索引选 **HNSW**
   （空表可建、增量构建，规避 ivfflat 预训练 lists 问题）。
5. ✅ 三个 Repository + UoW 接线（含 `tenant_id` 过滤）。

**验证（policy-postgres，已重建 api 镜像）**：`alembic upgrade head` 成功，三表 +
HNSW 余弦索引建成；仓库往返（写入/读取/列表/向量检索 sim=1.0/租户隔离/级联删除）
全通过；`import app.main` 应用启动不报错。DB 现处 head `f6a7b8c9d0e1`。

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

1. R1 已提交在本分支 `feat/rag-r1-datamodel`，人工确认后合回 `main`。
2. 开 R2 分支，基于本刀的数据契约与仓库接口实现入库流水线
   （COS 上传→PyMuPDF 解析→分块→Embedding→`document_chunk.add_many` 落库），
   配 `Settings.embed_api_key` 真实值（写入 `.env`，勿入库）。
