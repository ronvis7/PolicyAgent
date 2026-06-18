# 跨租户隔离对撞探针（走查 #7 / 已知风险首条）

Issue：无
分支：`test/cross-tenant-isolation-probe`
更新时间：2026-06-18

## 背景 / 目标

STATUS「已知风险」首条长期是"后端多租户测试覆盖不足，跨租户读取风险**未系统验证**"，
也是端到端走查遗留的 #7（#1 仅侧面证明 join 用户被隔离，未专门双账号对撞）。
本轮把它做实：一个可重复运行的对撞探针，注册两个独立组织 A/B，用 B 的令牌系统性
攻击 A 的资源，断言一律被隔离。

## 交付物

`scripts/cross-tenant-probe.ps1`（PowerShell 5.1 兼容，存为 UTF-8 BOM）。
- 注册 A/B 两个 owner（一次性 `probe-*@example.com`，create 模式各建自己组织）。
- 每个越权断言前都有一条**控制组**（owner 自己能访问），排除"资源根本没建成功导致 404"的假阴性。
- `-BaseUrl` 默认 `http://localhost:8888/api`，开头 `/status` 健康检查；全绿 exit 0，有泄漏 exit 1。

## 结果：18 项全绿（连 .222 真机）

| 维度 | 越权操作 | 期望 | 实测 |
|---|---|---|---|
| 会话 | B 读/删 A 的 session id | 404、A 的仍在 | PASS |
| 知识库 | B 读/删 A 的 kb id | 404、A 的仍在 | PASS |
| 企业档案 | B `GET /enterprise-profile` | 读自己的、不含 A 机密值 | PASS |
| 成员 | B 拿 A 的 `membership_id` 改角色/移除 | 403/404、A 成员仍在 | PASS |
| 参数注入 | B 带 `?tenant_id=A` 列会话 | query 覆盖无效 | PASS |
| 未认证 | 无令牌访问 | 401 | PASS |

机制印证：Repository 层强制 `WHERE tenant_id`；跨租户用 **404 而非 403**（不泄漏存在性）；
`membership_id` 等按-id 操作在服务层靠 `tenant_id` 兜住；ADR-002「query 不能覆盖当前租户」成立。

## 过程中的两个坑（均为探针自身缺陷，非产品问题）

1. **PS 5.1 请求体/响应中文编码**：`Invoke-RestMethod` 默认按 ASCII 编码请求体（中文变 `?`），
   响应又按 Latin1 解码（mojibake）。修法：请求体显式 `UTF8.GetBytes` + `charset=utf-8`；
   隔离断言改用纯 ASCII 机密值（不依赖中文）。浏览器前端无此问题。
2. **PS 标量 `.Count` 陷阱**：`Where-Object` 命中单个对象时返回标量而非数组，`.Count` 取到 `$null`，
   `$null -gt 0` 为 false → 假失败。修法：`@(...).Count` 强制数组化。

## 清理

探针用一次性账号，跑后用 api 容器内 async engine 按 `email LIKE 'probe-%@example.com'`
反查 owner 租户、顺依赖链（document_chunks→…→tenants→users）事务删除。
本轮 3 次成功跑共 6 users/6 tenants 全部清除，**共享库无残留**。复用命令见对话记录。

## 待续 / 下一步

1. **探针尚未覆盖**：Feed 条目改状态、租户 LLM key 读取、文件下载、会话 chat/stop/bind-kb
   （同源 `current_user.tenant_id` 守卫，风险同源）。值得补进探针闭合。
2. **自动化路线（治本）**：探针是手动对撞、未进 CI。STATUS 风险已降级但保留"自动化覆盖不足"。
   要根治需在 `api/tests/conftest.py` 补 DB + 双租户 token fixture，把隔离矩阵写成可回归 pytest
   集成用例（需真 PostgreSQL，SQLite 无 pgvector）。
3. 走查 #5（资质差距分析）、#6（Agent 问答 RAG）仍未正式过。
