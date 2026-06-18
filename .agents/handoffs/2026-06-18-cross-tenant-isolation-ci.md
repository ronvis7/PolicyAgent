# 跨租户隔离自动化测试进 CI

Issue：无
分支：`feat/cross-tenant-isolation-ci` → **PR 待开**
关联：handoff `2026-06-18-cross-tenant-isolation-probe`（手动探针）、ADR 002 租户上下文取自令牌
更新时间：2026-06-18

## 背景

跨租户隔离此前只有**手动**对撞探针 `scripts/cross-tenant-probe.ps1`（连真实运行栈、18 项），
**未进 CI**；且 STATUS 已知风险列出 Feed 改状态、文件下载等同源守卫面未纳入探针。PR #44
文件下载 401 又印证了文件面缺自动化回归保护。本次把隔离断言**自动化并纳入 CI 门禁**。

## 交付

**离线 endpoint 级隔离测试**（`api/tests/app/isolation/`）：
- `conftest.py`：
  - `_InMemoryUoW` + 各内存仓储（session/knowledge_base/enterprise_profile/feed/file），
    `get_by_id` 等按 `tenant_id` 过滤，**镜像真实 SQL 的隔离 WHERE**；可重复 `async with`
    （SessionService/FileService 构造时建一次 UoW 反复复用）。
  - `client` fixture：`TestClient(app)` **不进上下文管理器 → 不触发 lifespan**（不连 DB/Redis/COS）；
    `app.dependency_overrides` 覆盖 `get_token_service`（假 token→claims，使真实 `get_current_user`
    仍跑、覆盖"无 token→401"）+ 各 service provider 接入同一共享内存 UoW（A/B 两租户种子）。
- `test_cross_tenant_isolation.py`（9 条）：会话读/删、知识库读/删、企业档案不串、**Feed 改状态**、
  **文件下载** 均"跨租户→404 + 本租户→成功"双向断言；无 token→401、坏令牌→401。

**CI 扩面**（`.github/workflows/ci.yml`）：backend job 的 Unit tests 从 `pytest tests/app/domain`
改为 `pytest tests --ignore=tests/app/interfaces/endpoints/test_status_routes.py`——跑全部离线测试
（领域单元 + 应用服务 fake-UoW 测试 + 隔离 endpoint 测试），唯一忽略经 lifespan 连真库的
`test_get_status`。本地等效命令 **205 passed**。

## 边界 / 局限

- 内存仓储忠实复现"端点/服务是否以 `current_user.tenant_id` 作用域"这一层回归（即此前 bug 的高发面：
  端点用客户端输入还是令牌租户、服务有没有把 tenant_id 传给仓储）。**仓储 SQL 层 WHERE 子句回归**
  （某仓储漏掉 tenant 过滤）测不到——那需 **DB-in-CI 集成测试**（真 Postgres service 容器 + 真仓储），
  是后续独立项（CI 注释里"待接入 service 容器"指此）。
- 本批覆盖 会话/知识库/企业档案/Feed/文件下载/认证；**仍未自动化**：成员按 membership_id 横向越权、
  租户 LLM key 读取、会话 chat/stop/bind-kb（同源守卫，可按本套件模式续加）。手动探针仍是更全的
  真机校验，二者互补。

## 待续

- 续加成员/租户 LLM key/会话子资源的隔离用例（复用 `conftest.py` 的内存 UoW 模式）。
- DB-in-CI 集成测试（Postgres+pgvector service 容器 + alembic + 真仓储），把 SQL 层隔离与
  `test_get_status` 一并纳入门禁。
