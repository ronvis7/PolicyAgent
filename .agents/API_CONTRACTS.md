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

## 待实现知识库接口

以下为前后端并行开发基线，PR 实现前可细化字段，但不得静默改变资源语义。

- `GET /api/knowledge-bases`
- `POST /api/knowledge-bases`
- `GET /api/knowledge-bases/{kb_id}`
- `DELETE /api/knowledge-bases/{kb_id}`
- `POST /api/knowledge-bases/{kb_id}/documents`
- `GET /api/knowledge-bases/{kb_id}/documents`
- `GET /api/knowledge-bases/{kb_id}/documents/{document_id}`
- `POST /api/knowledge-bases/{kb_id}/search`

检索请求建议：

```json
{
  "query": "企业申请该政策需要满足什么条件？",
  "top_k": 5
}
```

检索结果至少返回：

```json
{
  "chunk_id": "chunk-id",
  "document_id": "document-id",
  "document_name": "policy.pdf",
  "content": "命中的政策片段",
  "score": 0.91,
  "page": 3,
  "source_url": null
}
```

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
