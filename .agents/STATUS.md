# 当前状态

最后更新：2026-06-13

## 仓库状态

- 主仓库：`policy_manus`，当前分支 `main`，工作区干净。
- `main` 已合入 R1+R2+R3（PR #1/#2/#3）。

## 已完成

> 细节以 `git log` 为准，本节只记里程碑。

- 多租户后端闭环：tenants/users/memberships + JWT + 租户切换；sessions/files/平台配置隔离。
- 前端认证闭环：登录/注册、Token 存储与 401 刷新、路由守卫、租户切换器、平台模型 API 配置页。
- Docker Compose 全量构建启动验证（`policy-*` 资源，库名 `policy_manus`）；Alembic 读统一运行时配置。
- `.agents/` 协作记忆体系。
- **RAG R1**：三表 + pgvector 向量存储 + 知识库管理 REST 端点。
- **RAG R2**：入库流水线（解析→分块→Embedding→落库）。
- **RAG R3**：`KnowledgeBaseTool` 接入 Agent，自主检索 + 带来源（文件名/页码/相似度）作答，引用经 SSE 渲染来源卡片。
- **RAG R4**：知识库管理前端页（`/knowledge`：建库/上传/FileStatus 进度轮询/删除，独立非聊天模块）。已真机联调通过（建库→上传→indexed、级联删除、页面 SSR 均 OK），并修复删除端点 `Response[None]` 致 500 的后端 bug（`feat/rag-r4-knowledge-ui` 分支）。
- **会话级 KB scope 选择器**：Session 加 `knowledge_base_id` 列 + 迁移（FK ON DELETE SET NULL）+ 绑定端点 `POST /sessions/{id}/knowledge-base` + 聊天输入区选择器。绑定为**硬限定**（覆盖 Agent 自选）。门禁全绿，迁移已真机执行落库（`a1b2c3d4e5f6 head`），UI 功能性回归由项目组自测。
- **共享开发数据库**：远程 PostgreSQL + pgvector 通过 SSH 隧道接入；统一启动脚本支持远程优先、本地强制和远程不可用自动回退。
- **数据库备份**：服务器端 cron 每天 03:30 `pg_dump -Fc` 留 7 天（`/opt/policy-postgres/backup.sh`）；本地 `scripts/db-dump.ps1` 经隧道拉取快照存档（留 14 份）。详见 handoff `2026-06-13-db-backup`。
- **租户级 LLM key + 成员管理（P4 BYO key / P6 RBAC）**：LLM 配置由平台统一改为按租户隔离（`tenant_settings` 表 + 迁移 `b2c3d4e5f6a7`），组织 owner/admin 在设置页配自己组织的 key，未配回落平台默认；Agent 运行时按当前登录租户取 key。`/app-config/llm` 门禁从平台管理员改为组织 owner/admin（拆到 `tenant_llm_routes`）。新增成员管理 `/members`（列表/按邮箱加已注册用户/改角色/移除，`MembershipService`）。前端：设置弹窗按角色过滤标签页 + 新增「组织成员」页，设置入口对 owner/admin 开放。16 个离线单元测试绿，后端导入/前端 tsc+eslint 全绿。**分支 `feat/tenant-llm-key-and-membership`，迁移未在真机执行**（需 DB 连通后随 api 启动自动 upgrade）。
- **注册重构 + 加入审批（同分支）**：注册拆「创建组织/加入组织」两入口；共享组织名应用层唯一、首个创建者永久 owner；加入＝自动建个人工作区（owner，未批准前用自己 key）+ 对目标组织建 `pending` 申请，owner/admin 审批通过才成正式成员。新增 `Tenant.is_personal`（迁移 `c4d5e6f7a8b9`）、`MembershipStatus.PENDING`、公开 `GET /auth/orgs` 检索、`/members/requests|approve|reject`。前端注册页 create/join 切换 + 组织检索、成员页待审批区。服务层单测 28 绿、前端 tsc/eslint 绿。**存量重复同名组织待 DB 连通后人工去重**。
- **企业档案 ①（结构化档案）**：产品转向"以企业为主体的主动情报服务"主线（企业档案→公开政策库→匹配→工作台 Feed→接问AI/报告）的第①步。每租户一条结构化档案（企业名/地区默认无锡新吴区/行业/规模/主营业务/资质·技术域·关键词），沿用 `tenant_settings` 单记录模式；`GET` 成员可读、`PUT` 限 owner/admin；前端 `/enterprise-profile` 档案页（owner/admin 可编辑、member 只读）+ 左栏入口。迁移 `d5e6f7a8b9c0`（**现 head**，纯新增表）。服务层单测 6 绿、全量 34 绿，前端 tsc/eslint 绿。**分支 `feat/enterprise-profile`（PR 待合并），迁移已真机执行**（2026-06-14 远程库已升级、`enterprise_profiles` 表已建）。Agent 联网增强档案（①b）schema 预留未做。
- **企业档案 ①b（Agent 联网增强）**：档案页「AI 联网补全」——以企业名联网检索 + LLM 仅依据证据抽取结构化建议字段，回填表单供 owner/admin 审阅后保存（**不落库、非破坏式合并**）。复用现有 `SearchEngine`/`OpenAILLM`(租户级 key)/`RepairJSONParser`，零新基础设施、零迁移。`POST /enterprise-profile/enrich`（owner/admin）。服务层单测 8 绿、全量 42 绿，前端 tsc/eslint 绿。**分支 `feat/enterprise-profile-enrich`，PR #11 待合并。**
- **公开政策库 ②（爬取+结构化入库+向量双写）**：主线第②步。爬无锡新吴区门户「政策文件」栏目（逆向 JSON 接口 `/info_open/search`，零 Playwright）→ upsert 入 `policies` 全局表（无 tenant，source_url 去重）→ 正文复用 RAG 流水线 embedding 进全局公开库（`knowledge_base.is_public` + 系统租户 `public`）。`GET /policies` 分页浏览（所有登录用户），前端 `/policies` 页 + 左栏入口；手动脚本 `scripts/crawl_wnd_policies.py`。迁移 `e6f7a8b9c0d1`（**现 head**：policies 表 + is_public + 播种 public 租户）。爬虫解析单测 6 + 服务/入库 6，全量 53 绿；实弹试爬通过；前端 tsc/eslint 绿。**分支 `feat/public-policy-crawl`（PR 待建），迁移未真机执行。** 匹配③/Feed④及公开库检索接入 Agent 后置。详见 handoff `2026-06-14-public-policy-crawl`。

## 未完成
- 可选：聊天内问政策验证引用、单文件删除端点、上传前端校验、app 日志输出到 stdout。
- 前端认证闭环真机联调；多租户自动化测试。
- 成员管理已实现基础闭环（加/改角色/移除/审批加入申请），尚缺：所有权转移、最后一名 owner 保护的更细规则。
- **存量重复同名组织清理**（历史 register 产生的同名租户，如两个「重庆理工大学」）待 DB 连通后人工去重；组织名 DB 唯一索引待去重后补。
- 报告生成流水线；GitHub Actions 与分支保护。
- 公开政策库②已交付（爬取+入库+向量双写），**迁移与真机入库待执行**；公开库语义检索接入 Agent 属③。

## 当前最高优先级

1. ③ 匹配（企业档案 × 公开政策）→ ④ 工作台 Feed（主线推进）。
2. 公开政策库②真机：迁移 upgrade + 脚本试爬落库 + `/policies` UI 联调。
3. 报告生成流水线。

## 已知风险

- 后端多租户测试覆盖不足，跨租户读取风险未系统验证。
- `.env`（腾讯 COS、`EMBED_API_KEY`）与 `api/config.yaml` 是 Docker 启动前置；含真实机密，保持 gitignored。
- 共享远程数据库依赖每台开发机的一次性 SSH 密钥和 `.env.remote` 配置；不同分支不得并发执行不兼容迁移。
- 检索默认全库，租户库多时为顺序循环，规模大需批量/并发或会话级 scope 收窄。
- 十天范围紧，新增基础设施须直接服务主链路。

## 更新规则

只记录最新事实。任务细节放 GitHub Issue，临时交接放 `handoffs/`，架构原因放 `decisions/`。
