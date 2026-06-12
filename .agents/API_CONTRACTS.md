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

## 契约变更规则

- 先修改本文档，再提交后端和前端代码。
- 删除字段或改变语义属于破坏性变更，必须在 PR 中明确标记。
- 数据库内部字段不应直接泄露为前端契约。
