# Contest source data additions — 2026-07-17

`tenant_contest_sources` stores tenant-owned static HTML contest sources. It is always filtered by `tenant_id`; optional `preset_source_id` references a verified platform `contest_sources` row when the tenant follows a regional preset.

`tenant_contest_source_items` links a tenant source to global `policies`, with unique `(tenant_id, source_id, policy_id)`. `contest_runs` stores source/discovery execution state and counts, indexed by `(tenant_id, kind, target_id, started_at)`.

`origin_type="tenant"` policy rows must never appear in normal public-policy/RAG queries. Contest list and detail access additionally verify the source-item link belongs to the current tenant.

# 数据模型与隔离规则

## 已有核心模型

### Tenant

企业组织。当前包含名称、slug、套餐和状态。

### User

全局身份。一个用户可通过 Membership 加入多个租户。

### Membership

连接 User 和 Tenant，角色至少包含 owner、admin、member。

### Session

Agent 会话。必须带 `tenant_id` 和 `owner_id`。

### File

用户上传或 Agent 生成的文件。必须带 `tenant_id`，对象存储路径也必须包含租户作用域。

## 待实现 RAG 模型

### KnowledgeBase

- `id`
- `tenant_id`
- `name`
- `description`
- `type`
- `visibility`
- `embedding_model`
- `chunk_strategy`
- `status`
- `created_by`
- `created_at`
- `updated_at`

租户内名称可唯一，不要求跨租户唯一。

### KnowledgeDocument

- `id`
- `tenant_id`
- `knowledge_base_id`
- `original_name`
- `storage_key`
- `source_url`
- `content_hash`
- `mime_type`
- `size`
- `status`
- `error_message`
- `metadata`
- `created_by`
- `created_at`
- `updated_at`

状态建议：`uploaded/parsing/indexing/ready/failed`。

### KnowledgeChunk

- `id`
- `tenant_id`
- `knowledge_base_id`
- `document_id`
- `chunk_index`
- `content`
- `page`
- `start_offset`
- `end_offset`
- `metadata`
- `embedding`
- `created_at`

### IngestionJob

记录文档解析和索引进度，状态建议为 `pending/running/completed/failed`。

### RetrievalLog

记录查询、知识库范围、命中 chunk、耗时和用户反馈，用于调试及后续评估。

## 待实现政策模型

第一版允许政策作为知识文档，并通过 metadata 保存结构化字段。需要业务检索时再增加 `PolicyDocument`：

- 标题、文号、发布机关
- 发布、生效和失效日期
- 地区、行业和政策层级
- 原文 URL、正文哈希和版本
- 申报对象、条件、材料和截止日期

## 赛事中心模型

公开 `policies` 内容增加 `item_type`（`policy`/`competition`）、`origin_type`（`official`/`web`）和
`source_name`。赛事仍以 `source_url` 全局去重，避免同一公开赛事被多个关键词或租户重复写入。

### ContestSource

平台级官方赛事来源：`id`、`key`、`name`、`region`、`home_url`、`adapter_type`、`adapter_config`、
`enabled`、`created_at`、`updated_at`。不带 `tenant_id`；仅平台管理员可写。`adapter_type` 必须是平台已验证
的爬虫模板，`adapter_config` 保存该模板的非机密栏目参数。

### ContestSubscription

企业全网赛事关键词订阅：`id`、`tenant_id`、`keyword`、`enabled`、`last_run_at`、`created_at`、
`updated_at`。`tenant_id` 不可空且建索引；租户内 `(tenant_id, keyword)` 唯一。公开赛事不记录或返回订阅
所属租户，避免泄露企业关注方向。

### ContestDiscoveryHit

全网发现命中记录：`id`、`tenant_id`、`subscription_id`、`policy_id`、`created_at`。
这是租户私有数据，`tenant_id` 必须过滤；`(tenant_id, policy_id)` 唯一，使公开赛事可以全局只保存一份，
同时允许不同企业各自收到一次通知，而同一企业的多个关键词不会重复推送。

### FeedItem 赛事提醒语义

`policy_matches`（领域模型为 `FeedItem`）已带 `tenant_id`、`policy_id`、`type` 与 `status`。赛事飞书推送只选择本租户本次新建且 `type=competition` 的 Feed 条目；`ignored`/`applied` 状态在后续快照更新时保留，因此不会因重爬重新提醒。该优化不增加新表或迁移。

对于 `deadline_status=unknown` 的赛事，Feed 仅保留发布时间 45 天以内的条目；`rolling` 或未来明确截止的赛事按原有时效规则保留。

## 待实现报告模型

### Report

- `id`
- `tenant_id`
- `owner_id`
- `title`
- `template_type`
- `status`
- `input_snapshot`
- `evidence_snapshot`
- `content`
- `output_file_id`
- `error_message`
- `created_at`
- `updated_at`

## 强制隔离规则

- 所有租户业务表必须有不可空 `tenant_id` 和索引。
- 外键查询必须同时验证目标资源属于当前租户。
- 唯一约束通常包含 `tenant_id`。
- COS key、Redis key、任务 ID 和动态 Sandbox 名称包含租户作用域。
- 平台管理员的跨租户能力必须通过显式管理接口，不能绕过普通 Repository 默认过滤。
- 删除租户数据时必须考虑数据库、向量、COS、Redis 和沙箱产物。

