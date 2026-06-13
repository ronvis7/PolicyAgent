# 租户级 LLM key + 组织成员管理

Issue：待创建
分支：`feat/tenant-llm-key-and-membership`（未合并、迁移未真机执行）
更新时间：2026-06-13

## 背景

原设计 LLM api_key 为平台统一一把、仅 `is_platform_admin`（需手动改库授权）可改；组织角色 owner/admin 形同虚设，成员管理未做。用户诉求：每组织自配 key、注册者即可配置、owner 能把成员设为管理员。

## 决策（2026-06-13 与用户敲定）

1. **api_key 按组织隔离（BYO key）**，组织未配时回落 config.yaml 平台默认 key。
2. **仅 LLM 租户化**，MCP/A2A/Agent 通用参数仍平台级（platform_admin）。
3. **成员"邀请" = 按邮箱加已注册用户**（无邮件系统，最简可用）。

详见 `.agents/` 记忆 `multitenancy-decisions` 第 4 点（已更新）。

## 已完成

### 后端
- 新增 `tenant_settings` 表（tenant_id PK/FK→tenants CASCADE，llm_config JSONB 可空）+ 迁移 `b2c3d4e5f6a7`（down_revision=`a1b2c3d4e5f6`，单一 head）。
- domain/infra 模型 `tenant_settings.py`、`TenantSettingsRepository` + DB 实现，接入 UoW（`uow.tenant_settings`）。
- `TenantSettingsService`：`resolve_llm_config`/`get_llm_config`/`update_llm_config`（空 api_key 保留既有→平台默认；不可变更新）。
- `service_dependencies.get_agent_service` 改 async，按当前令牌租户解析 LLM；抽出 `_build_agent_service`；新增 `get_default_agent_service`（供 main.py 关闭钩子无上下文调用）、`_get_optional_tenant_id`（本模块内定义以避免与 auth_dependencies 循环导入）。
- LLM 路由拆到 `tenant_llm_routes.py`，门禁 `require_role(owner, admin)`；`app_config_routes` 去掉 LLM、其余仍 `require_platform_admin`。
- 成员管理 `MembershipService` + `membership_routes.py`（`GET/POST /members`、`POST /members/{id}/role`、`POST /members/{id}/delete`）。规则：owner 不可改/移除，仅可赋 admin/member，按 tenant 范围加载隔离他租户，移除为软删 disabled，重加复用记录重新激活。
- `PublicLLMConfig` 增 `is_custom` 标识。

### 前端
- `lib/api/membership.ts`（membershipApi + 类型）并导出；`LLMConfig.is_custom`。
- `manus-settings.tsx` 按角色过滤标签页（LLM/组织成员=org，通用/A2A/MCP=platform），数据拉取按角色避免 403，members 标签页隐藏保存按钮。
- 新增 `members-setting.tsx`（列表/加/设管理员/移除，owner 与本人行锁定）。
- `chat-header.tsx`/`left-panel.tsx` 设置入口对 owner/admin 开放。

## 验证

- 后端：`py_compile` 全过；`import app.interfaces.endpoints.routes` 与 `app.main` 正常（无循环导入）；`alembic heads` 单一 `b2c3d4e5f6a7`。
- 单测：`tests/app/application/services/`（tenant_settings + membership）共 **16 passed**（内存假 UoW，asyncio.run 驱动，不依赖真库）。
- 前端：`tsc --noEmit` exit 0；`eslint` exit 0。

## 剩余事项

- **迁移未真机执行**：DB 连通后随 api 启动自动 `upgrade head`；对共享远程库为新增表、向后兼容。
- 重建容器使新代码生效：`dev-up.cmd -Mode Remote -Build`。
- 真机联调：owner 配本组织 key→Agent 是否用该 key；跨组织隔离；成员加/改/移除 UI。
- 可选增强：邀请待接受流程、所有权转移、端到端接口测试（现有 client fixture 依赖真实 DB/Redis/COS）。

## 风险

- `get_agent_service` 改 async：已确认仅 session 路由（DI 注入）与 main.py（改用 `get_default_agent_service`）两处消费，无遗漏。
- 多分支并发对共享库迁移的约束仍适用；本迁移为纯新增表，冲突风险低。

---

## 追加：注册重构 + 加入审批（2026-06-13 同分支）

### 背景
用户实测发现：注册时填已存在的组织名（如「重庆理工大学」），会**新建一个同名组织并让你当 owner**，而非加入已有组织——因为 `register` 一律新建租户、组织名无唯一约束。

### 决策
- 注册拆「**创建组织 / 加入组织**」两入口；共享组织名规范化后唯一，首个创建者永久 owner。
- 加入＝自助申请：注册时自动建**个人工作区**（owner、激活租户，未批准前用自己的 key），并对目标组织建 `pending` 申请，owner/admin 审批通过才成正式成员。
- 已存在的重复同名组织：保留最早、清掉重复（**待 DB 连通后人工执行**，未做）。

### 已完成
- `Tenant` 加 `is_personal`（domain+ORM+迁移 `c4d5e6f7a8b9`，down=`b2c3d4e5f6a7`，现 head）；`MembershipStatus` 加 `PENDING`。
- `TenantRepository.get_shared_by_name`（规范化唯一性）/`list_shared`（加入检索）+ DB 实现。
- `AuthService.register(mode, org_name, org_id)` 拆 `_register_create_org`/`_register_join_org`；`list_joinable_orgs`。组织名唯一在**应用层**校验（存量有历史重复，暂不加 DB 唯一索引以免阻塞启动）。
- 公开端点 `GET /auth/orgs?q=`（免登录检索可加入组织）。
- `MembershipService` 加 `list_pending_requests`/`approve_request`/`reject_request`；`list_members` 改为只列 active。路由 `GET /members/requests`、`POST /members/{id}/approve|reject`（owner/admin）。
- 前端：注册页 create/join 切换 + 组织防抖检索选择；成员页顶部「待审批加入申请」区（批准/拒绝）；`authApi.listOrgs`、`membershipApi.listRequests/approve/reject`、`RegisterParams.mode/org_id`。

### 验证
- 后端 `py_compile`/导入 OK；`alembic heads` 单一 `c4d5e6f7a8b9`；服务层单测 **28 passed**（新增 register 7 + 审批 5）。
- 前端 `tsc`/`eslint` exit 0。

### 剩余/注意
- **存量重复同名组织未清理**（待 DB 连通）；DB 唯一索引待去重后另起迁移补。
- 加入获批后，用户需重新登录/`/auth/me` 刷新才会在租户切换器看到新组织（pending 不进 active 列表）。
- 组织名唯一仅应用层校验，并发创建同名有极小竞态（小规模可接受）。
