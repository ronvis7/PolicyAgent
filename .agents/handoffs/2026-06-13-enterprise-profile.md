# 企业档案 ①（结构化档案：表单 + 存储 + 档案页）

Issue：待创建
分支：`feat/enterprise-profile`（PR 待合并；迁移已真机执行）
更新时间：2026-06-14

## 目标

产品形态转向"以企业为主体的主动情报服务"。主线：**企业档案 → 公开政策库(爬取入库) → 匹配 → 工作台 Feed → 接问AI/报告**。
本次只做主线第①步、且只做结构化档案的"表单 + 存储 + 档案页"（不依赖联网搜索）。Agent 联网增强档案（①b）schema 预留、本期不做。

## 决策（2026-06-13 与用户敲定）

1. 首页将改为工作台/Feed（广域，主动推送），聊天降级为深挖入口（细域）——本次未动首页，仅建档案。
2. 政策库后续做成 **公开(全局共享) + 租户私有** 双层；公开库爬取入库为主线 ②。
3. 机会来源 v1 = **爬取权威源 + 结构化入库**（不赌实时全网搜）；先做政策，赛事后置。
4. 抓取地区锁定 **江苏无锡·新吴区**（用户工作地，高新区政策最密集）。
5. 档案首版 = **表单打底**（Agent 增强为 ①b）；字段用**精简 MVP 集**。

## 已完成

### 后端（严格沿用 `tenant_settings` 单租户单记录模式）
- 域模型 `domain/models/enterprise_profile.py`：`EnterpriseProfile` + `EnterpriseScale` 枚举；默认地区江苏省/无锡市/新吴区。
- 仓储协议 `domain/repositories/enterprise_profile_repository.py`（`get_by_tenant`/`save`）。
- ORM `infrastructure/models/enterprise_profile.py`：表 `enterprise_profiles`，`tenant_id` PK+FK CASCADE；标量列 + 列表型字段(资质/技术域/关键词)收进 `attributes`(JSONB)；`from_domain`/`to_domain`/`update_from_domain`。已在 `infrastructure/models/__init__.py` 导出。
- DB 仓储 `infrastructure/repositories/db_enterprise_profile_repository.py`（upsert）。
- UoW 接线：`uow.py` 加 `enterprise_profile` 属性；`db_uow.py.__aenter__` 实例化。
- 服务 `application/services/enterprise_profile_service.py`：`get_profile`（无则返回带默认地区空档案）、`update_profile`（整体覆盖 + `model_copy`；强制以上下文 tenant_id 落库防越权、保留 created_at）。
- Schema `interfaces/schemas/enterprise_profile.py`：`UpdateEnterpriseProfileRequest`（长度上限校验 + 标签去空去重，上限 50/标签 64 字）、`EnterpriseProfileResponse`。
- 路由 `interfaces/endpoints/enterprise_profile_routes.py`：`GET /enterprise-profile`（成员可读）、`PUT /enterprise-profile`（owner/admin）。已注册到 `routes.py`；工厂 `get_enterprise_profile_service` 在 `service_dependencies.py`。

### 前端（App Router + `lib/api/fetch` + shadcn）
- `lib/api/profile.ts`：`profileApi.get/update` + 类型；`lib/api/index.ts` 导出。
- 档案页 `app/enterprise-profile/page.tsx`：表单（企业名/地区三段/行业/规模 native select/主营业务/资质·技术域·关键词标签输入）；`useAuth().role` 门禁，owner/admin 可编辑保存、member 只读；内联 `TagInput`（无 shadcn Select 组件，规模用 native `<select>`）。
- 导航 `components/left-panel.tsx`：知识库上方加"企业档案"入口（所有登录用户可见）。

## 接口与迁移

- `GET /enterprise-profile` → `Response[EnterpriseProfileResponse]`。
- `PUT /enterprise-profile` body=`UpdateEnterpriseProfileRequest` → 同响应；仅 owner/admin。
- 迁移 `alembic/versions/d5e6f7a8b9c0_add_enterprise_profile.py`（down=`c4d5e6f7a8b9`，**现 head**）；纯新增表、向后兼容。

## 验证

- 后端 `py_compile` 全过；`import app.interfaces.endpoints.routes; import app.main` 无循环导入；`alembic heads` 单一 `d5e6f7a8b9c0`。
- 单测 `tests/.../test_enterprise_profile_service.py` **6 passed**；服务层全量 **34 passed**（含既有 28）。
- 前端 `tsc --noEmit` exit 0、`eslint`（改动文件）exit 0。
- 真机：`dev-up.cmd -Mode Remote -Build` 启动成功，远程库已升级到 `d5e6f7a8b9c0`、`enterprise_profiles` 表已建（2026-06-14 SSH 核验）。

## 未完成 / 下一步

- **迁移已真机执行**：远程库 `alembic_head=d5e6f7a8b9c0`、`enterprise_profiles` 表已存在（2026-06-14 经 `dev-up.cmd -Mode Remote -Build` 随 api 启动自动 upgrade）。
- 真机 UI 联调（待项目组自测）：owner 填写保存→刷新仍在；切 member 账号确认只读；跨租户隔离。
- 下一步主线：①b Agent 联网增强档案 → ② 无锡新吴区公开政策爬取/结构化入库（全局库）→ ③ 匹配 → ④ 工作台 Feed。

## 风险

- `GET/PUT` 路径用空 path + 前缀（`/enterprise-profile`，无尾斜杠），前端调用一致。
- 多分支并发对共享库迁移的约束仍适用；本迁移为纯新增表，冲突风险低。
