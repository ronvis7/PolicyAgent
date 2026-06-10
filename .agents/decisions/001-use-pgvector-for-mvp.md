# ADR 001：MVP 使用 pgvector

状态：已决定

日期：2026-06-09

## 背景

项目只有两名开发者和不足十天的交付周期。参考项目 Yuxi 使用 Milvus、etcd、MinIO 和 Neo4j，但当前 PolicyManus 已使用 PostgreSQL 和 COS。

## 决策

MVP 使用 PostgreSQL + pgvector 存储向量。通过领域接口封装向量写入、删除和检索，不让应用服务依赖 pgvector 特有 SQL。

## 原因

- 减少部署服务和故障点。
- 复用现有 PostgreSQL 的租户事务与备份体系。
- 对演示和早期数据规模足够。
- 后续仍可迁移到 Milvus 或其他向量数据库。

## 后果

- Docker PostgreSQL 镜像需要支持 pgvector 扩展。
- Alembic 负责扩展和向量列迁移。
- 大规模数据和复杂混合检索不是本期目标。

