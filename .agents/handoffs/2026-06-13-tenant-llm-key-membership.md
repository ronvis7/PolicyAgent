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
