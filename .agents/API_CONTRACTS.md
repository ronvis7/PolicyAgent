# Contest source additions — 2026-07-17

- Regional portal suggestions use a two-pass public-government search (department portal, then contest notice) and return candidates for preflight; no suggestion is enabled automatically.
- `GET/POST/PATCH/DELETE /api/tenant/contest-sources`: tenant owner/admin private source management.
- `POST /api/tenant/contest-sources/{id}/preflight`, `POST /api/tenant/contest-sources/{id}/ingest`, and `GET /api/tenant/contest-sources/{id}/runs`: tenant-scoped preflight, manual ingest, and the latest ten runs.
- `POST /api/tenant/contest-sources/suggestions` accepts `{ "region": string }` and returns at most three public-portal candidates. A candidate only fills the UI; it is not saved or enabled until explicit creation and preflight.
- Tenant-source creation can include `preset_source_id` to follow a verified platform official source for the selected region.
- `POST /api/contest-subscriptions/{id}/discover` starts one discovery run. `GET /api/contest-subscriptions/{id}/runs` returns the latest ten runs. Both enforce the server-side five-minute cooldown.
- `GET /api/contests` may return `origin: "tenant"`; such entries are visible only to the owning tenant. Web discovery excludes all configured official-source hosts.

# API 契约

本文档记录前后端并行开发所需的稳定契约。实际实现变化后必须同步更新。

## 通用约定

- API 前缀：`/api`
- 响应结构：`{ "code": number, "msg": string, "data": any }`
- 认证头：`Authorization: Bearer <access_token>`
- 租户上下文来自访问令牌，不接受客户端通过普通查询参数覆盖。
- 401 表示未登录或令牌失效；403 表示已登录但权限不足。

## 已有认证接口

### `POST /api/auth/register`

输入：

```json
{
  "email": "user@example.com",
  "password": "password",
  "display_name": "User",
  "org_name": "Example Corp"
}
```

### `POST /api/auth/login`

输入：

```json
{
  "email": "user@example.com",
  "password": "password"
}
```

### `POST /api/auth/refresh`

输入 refresh token，返回轮换后的 access token 和 refresh token。

### `POST /api/auth/logout`

吊销 refresh token。

### `POST /api/auth/switch-tenant`

输入：

```json
{
  "tenant_id": "target-tenant-id"
}
```

返回新租户上下文下的令牌对。

### `GET /api/auth/me`

返回当前用户、当前租户、角色和可访问租户列表。用户对象包含
`is_platform_admin`，前端据此显示平台级配置入口。

## 平台模型配置

以下接口仅允许平台管理员访问：

- `GET /api/app-config/llm`
- `POST /api/app-config/llm`

读取响应不包含 `api_key`，仅返回：

```json
{
  "base_url": "https://api.deepseek.com/",
  "model_name": "deepseek-chat",
  "temperature": 0.7,
  "max_tokens": 8192,
  "api_key_configured": false
}
```

更新时可提交 `api_key`；空字符串表示保留当前密钥。密钥不得通过读取接口回传。

## 知识库接口（已实现 R1+R2+R4）

均需登录，租户上下文来自访问令牌。资源以租户隔离。

- `GET /api/knowledge-bases` — 列出当前租户知识库
- `POST /api/knowledge-bases` — 新建，body `{ name, description? }`
- `GET /api/knowledge-bases/{kb_id}` — 详情
- `DELETE /api/knowledge-bases/{kb_id}` — 删除（级联清文件与切片）
- `POST /api/knowledge-bases/{kb_id}/files` — 上传文件（multipart `file`），后台异步解析入库
- `GET /api/knowledge-bases/{kb_id}/files` — 文件列表（含处理状态）

`KnowledgeBase` 返回：`{ id, tenant_id, owner_id, name, description, type, embedding_model, updated_at, created_at }`。

`KnowledgeFile` 返回：`{ id, tenant_id, knowledge_base_id, owner_id, file_id, filename, status, error_message, chunk_count, updated_at, created_at }`。
`status` 状态机：`uploaded → parsing → parsed → indexing → indexed`，失败分支 `error_parsing` / `error_indexing`。前端在存在处理中状态时轮询列表刷新进度。

**检索不走独立 REST**（ADR-002）：政策检索作为 Agent 工具 `knowledge_base_search` 在聊天流中调用，引用经 SSE `tool_content` 透传渲染来源卡片。详见 R3 交接。

### 会话级知识库 scope 绑定

- `POST /api/sessions/{session_id}/knowledge-base` — 绑定/解绑会话检索范围，body `{ knowledge_base_id: string | null }`；传 `null` 表示解绑（全库检索）。校验会话与目标知识库均归属当前租户。
- `GET /api/sessions/{session_id}` 响应新增 `knowledge_base_id` 字段（`null` = 全库）。

**绑定为硬限定**：会话绑定某库后，`knowledge_base_search` 工具忽略 Agent 自传的 `knowledge_base_id`，检索只在绑定库内进行；未绑定时维持默认全库检索。删除知识库会经 FK `ON DELETE SET NULL` 自动解绑相关会话。

## 待实现报告接口

- `POST /api/reports`
- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `GET /api/reports/{report_id}/status`
- `GET /api/reports/{report_id}/download`

报告创建输入至少包含企业材料、知识库范围和报告模板标识。报告状态使用 `pending/running/completed/failed`。

## 赛事中心（双来源）

赛事为全局公开内容；企业的关键词订阅与推送配置为租户数据，严格从访问令牌取得租户上下文。

- `GET /api/contests` — 分页浏览赛事中心。支持 `origin=official|web`、`region`、`source`、`keyword`、`active_only` 筛选。
- `GET /api/contests/{contest_id}` — 获取赛事详情和原文链接。
- `GET /api/contest-sources` — 列出平台维护的官方赛事来源及抓取状态。
- `GET/POST/PATCH/DELETE /api/contest-subscriptions` — 当前组织 owner/admin 管理本组织的全网赛事关键词订阅；响应不得泄露其他租户订阅。
- `GET/POST/PATCH/DELETE /api/platform/contest-sources` — 仅平台管理员管理官方来源；`POST /{id}/preflight` 为只读连通性预检，`POST /{id}/ingest` 手动触发抓取。

赛事列表项包含 `origin`（`official` 或 `web`）、`source_name`、`region`、`apply_deadline` 与 `source_url`。全网发现条目必须完成原文抓取、赛事/报名语义与时效校验后才可出现在该接口或触发推送。
同一原文按 `source_url` 全局去重；全网发现的通知命中记录仅在订阅租户内保存，接口不返回其他租户的关键词或命中状态。

## 飞书赛事机会通知

- 飞书仅推送当前租户新创建的 `FeedItem.type=competition`；Feed 是唯一准入结果，企业画像、关注地区、报名时效和已忽略状态均在推送前生效。
- 同一 `(tenant_id, policy_id)` 已存在于 Feed 时，即使后续重爬或重新入库也不会重复推送；每日重爬不再发送全量赛事或“0 条赛事”摘要。
- 卡片的“查看赛事机会”跳转 `/feed`；“不再提醒此赛事”跳转 `/feed?ignore={feed_item_id}`。用户登录后，前端调用既有 `POST /api/feed/{feed_item_id}/status`，body 为 `{ "status": "ignored" }`。
- 状态接口继续只以访问令牌中的租户处理条目；非本租户的 `feed_item_id` 返回 404，不能借飞书链接跨租户停止提醒。

## 契约变更规则

- 先修改本文档，再提交后端和前端代码。
- 删除字段或改变语义属于破坏性变更，必须在 PR 中明确标记。
- 数据库内部字段不应直接泄露为前端契约。
