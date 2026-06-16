# 当前状态

最后更新：2026-06-16

## 仓库状态

- 主仓库：`policy_manus`，当前分支 `main`（干净）。
- `main` 已合入 ②公开政策库（PR #12）+ ③政策匹配（PR #13）+ ④工作台 Feed（PR #16）+ 自助加入其他组织（PR #18）+ 公开政策库通用多区域框架（PR #19）+ ⑥资质 Phase 1（PR #21）+ **企业档案结构化字段 A0 + 资质能力②差距分析 A1（PR #22，2026-06-16 合并）**。
- **基建：共享 PostgreSQL 已从 `118.196.142.223`（停机）迁到 `118.196.142.222`**（部署/数据/备份逐项校验 + 全栈 Remote 真机走查通过，详见 handoff `2026-06-16-postgres-server-migration`）。

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
- **企业档案 ①b（Agent 联网增强）——已暂停**：档案页「AI 联网补全」，后改为与聊天同源的 agentic 研究（一次性沙箱+浏览器+多步 LLM，逐字段带来源）。机制全通（reasoning_content 回传、4 分钟超时均已修），但**真机实测效果极差、字段几乎全空**——根因是**没有可靠数据源**：Bing 抓取失效、天眼查/企查查等强反爬浏览器读不到。已用开关 `ENRICH_ENABLED=false`（`ui/.../enterprise-profile/page.tsx`）**隐藏按钮**，后端服务/端点/单测全保留。**复活条件**：接入正规搜索/企业数据 API（需 key），置 true 并把 `BingSearchEngine` 换掉。分支 `feat/enterprise-profile-enrich`（PR #11，**暂不合并**）。详见记忆 `search-and-enrichment`。
- **资质申报机会 ⑥ Phase 1（目录+匹配能力①+接入 ④ Feed）——已合并**：把「机会」从单一政策扩为多类，新增资质(qualification)作为 ④ Feed 第二类内容源。**目录即代码、不爬**：`infrastructure/data/qualification_catalog.py` 25 条结构化资质（国家/江苏省/无锡·新吴区/通用认证），每条带 `last_reviewed`+`disclaimer`。**能力①匹配**：纯函数 `qualification_matcher`（地区门槛 + 信号重合 + 前置资质 → 可申报/接近(差N项)，阈值 0.6）+ `QualificationService`。**接入 ④ Feed**：`FeedItem.from_qualification_match`（`policy_id` 复用资质 key、type=qualification）+ `FeedService` 可选 `qualification_service`，抓取/改档案后政策+资质一并物化、统一红点；**零迁移**（`policy_matches` 表 `type` 列既有、`policy_id` 无外键）。API `GET /qualifications` + `/{key}`；UI 资质机会页+Feed 类型徽章与详情分流+左栏入口，详情**强制免责声明+末次核对日期**（风险纪律）。单测 matcher 8+service 4+catalog 6+Feed 2，全量 **102 passed**；tsc/eslint 绿；`alembic heads` 仍 `f7a8b9c0d1e2`（无迁移）。**PR #21 已合并 main（2026-06-16）。** 详见 handoff `2026-06-15-qualification-opportunities`。
- **资质能力③ 材料/流程指引 Agent 工具 A2——本期交付**：⑥ 主线第三块。新增 Agent 工具 `QualificationTool`(`name=qualification`)接入聊天链路：`qualification_list`(按租户档案列可申报/接近候选)、`qualification_gap(key)`(差距分析 达标✓/不达标✗/待确认? + 缺前置 + `manual_review` 软条件)、`qualification_detail(key)`(材料/时间/政策依据/价值)。**分层干净**：工具内核全走 domain 纯函数(`match_qualifications`/`analyze_gap`)+ uow 读档案，不依赖 application/infrastructure；目录由构造链 `_build_agent_service`→`AgentService`→`AgentTaskRunner`→`PlannerReActFlow` 注入；租户由会话懒加载隔离(同 KnowledgeBaseTool)。gap/detail 强制带 `disclaimer`+`last_reviewed`，工具说明引导 Agent **结合 `knowledge_base_search` 取政策原文交叉核对**、把待确认/软条件交原文深化(混合引擎"软"半边)。**SSE 专属卡片**：新增 `QualificationToolContent` 事件类型 + runner 映射 + 前端 `qualification` ToolKind/`Award` 徽章/`QualificationPreview` 预览卡(逐条要点 + 琥珀色免责声明)。新增工具单测 8、**全量 142 passed**(1 error 为既有需真库 `test_get_status`)、tsc/eslint/build 绿、零迁移(`alembic head` 仍 `f7a8b9c0d1e2`)。**PR #24 已合并 main（2026-06-16）；全栈 Remote 真机走查通过**（连 .222：注册→存档案→建会话→聊天问"我能申报哪些资质/高企还差什么/要哪些材料"，Agent 自主依次调 `qualification_list`/`qualification_gap`/`qualification_detail` + `knowledge_base_search`；并经 `GET /qualifications/{key}/gap` 确定性复核"成立7年达标/科技人员8%不达标、5项 manual_review、disclaimer+last_reviewed 在位"。冒烟账号已事务删除清理）。详见 handoff `2026-06-16-qualification-guidance-tool`。
- **企业档案结构化字段 A0 + 资质能力②差距分析 A1——已合并**：⑥ 主线第二块。**A0**：档案新增 成立日期/总人数/研发人数/注册资本/营收/研发投入/发明专利/其他知识产权 8 字段（**手动填写**，避开 ①b 数据源难题），经既有 `attributes`(JSONB) **零迁移**承载，数值用 `Optional` 区分"未填写≠0"；请求 schema 非负+日期格式校验；档案页加「经营与研发指标」区。**A1（能力② 混合引擎结构化部分）**：`Qualification.structured_conditions`（`ConditionMetric` 指标+门槛+方向，占比/年限由档案推导）+ 纯函数 `domain/services/qualification_gap.py::analyze_gap` → 逐条 **达标/不达标/待确认(未填)**，**缺字段判待确认绝不误报不达标**；`manual_review` 收口无结构化对应的概要条件、`prerequisites_missing` 复用能力①。端点 `GET /qualifications/{key}/gap`（注册在 `/{key}` 前，强制 disclaimer+last_reviewed）；前端详情视图加「条件差距分析」区块（资质页+④Feed 复用）。**目录仅高企已结构化**（成立满1年+科技人员≥10%），其余 24 条待逐条**校对数值**后补。全量 **134 passed**、tsc/eslint/build 绿、零迁移（`alembic head` 仍 `f7a8b9c0d1e2`）。**PR #22 已合并 main（2026-06-16）；全栈 Remote 真机走查通过**（连 .222：注册→存档案 8 字段→读回一致→高企差距分析"成立7年达标/研发人员8%不达标"计算正确，冒烟账号已清理）。详见 handoff `2026-06-16-qualification-gap-analysis`。
- **工作台 Feed ④（物化政策信息流 + 未读红点）——已交付**：主线第④步。在 ③ 即时匹配之上物化 `policy_matches` 表（`UNIQUE(tenant_id, policy_id)`，计算快照落列免 N+1，状态机 unread/read/applied/ignored，**含 `type` 列为 ⑥ 资质/比赛预留**）。`FeedService.recompute_for_tenant`：新增→unread（驱动红点）、已存在只更新快照保留用户 status/created_at、跌出候选保留不删。**触发 (a) 抓取政策入库后 + (b) 改企业档案后**在端点排后台任务重算当前租户，(c) Feed 页「重新匹配」手动兜跨租户。端点 `/feed`（list/unread-count/recompute/mark-read/{id}/status，所有登录用户限当前租户）。前端 `/feed` 工作台页（状态筛选/重新匹配/已申报·忽略/详情弹窗复用 `/policies/{id}`）+ 左栏「工作台」入口未读红点（自定义事件 `feed:unread-changed` 同步）；**删除 `/matches` 页与「政策匹配」入口**。运维：`policy-api` healthcheck `start_period` 20s→120s（远程库冷启动不再被误判 unhealthy）。迁移 `f7a8b9c0d1e2`（**现 head**，纯新增表 + tenant_id/status 索引）。单测 FeedService 7 + 全量 **74 passed**；tsc/eslint 绿。**PR #16 已合并 main（2026-06-15），迁移已真机执行（远程库 `alembic current=f7a8b9c0d1e2`、`policy_matches` 表已建）、Docker 全栈健康。** 详见 handoff `2026-06-15-feed-impl`。
- **政策匹配 ③（企业档案 × 公开政策）——本期交付**：主线第③步。即时计算、不落表：按当前租户企业档案现算可申报政策候选。**两路融合**：①结构化命中（档案 `keywords/tech_domains/qualifications/industry` 词表落在政策 `title`(权重高)+`body_text`，归一化命中度 + 命中词）；②语义召回（档案画像 `industry+main_business+tech_domains+keywords` 拼查询 → embedding → 检索公开库 `public-policy-kb`/系统租户 `public` → 切片按 `source_url` 聚合回政策）；两路有序候选经 **RRF**（k=60）融合排序，输出带「推荐理由」（命中关键词/地区匹配/语义相关度）。纯函数内核 `domain/services/policy_matcher.py`（`extract_profile_terms`/`build_profile_query`/`region_matches`/`score_terms`/`structured_score`/`reciprocal_rank_fusion`）+ 应用服务 `policy_match_service.py`；端点 `GET /policies/match?top_k=N`（所有登录用户，限当前租户档案，**注册在 `/{policy_id}` 之前**避免被路径参数捕获）；仓储加 `list_candidates`/`list_by_source_urls`（语义回查批量 IN，无 N+1）。前端 `/matches` 候选页（分数/命中度/语义分/推荐理由/详情弹窗复用 `/policies/{id}`）+ 左栏「政策匹配」入口。**无新表、无迁移**（`alembic heads` 仍 `e6f7a8b9c0d1`）。单测：匹配器纯函数 10 + 服务 4，全量 **67 passed**（跳过需真库的 status）；`import app.main` OK；前端 tsc/eslint 绿。**决策**：即时计算（物化留作④Feed）、本期不含 Agent 接公开库（KnowledgeBaseTool 纳入 is_public 留作后续小分支）。**PR #13 已合并 main（2026-06-15），Docker 起栈连远程库 `/matches` 走查通过。** 详见 handoff `2026-06-15-policy-matching`。
- **公开政策库 ②（爬取+结构化入库+向量双写）**：主线第②步。爬无锡新吴区门户「政策文件」栏目（逆向 JSON 接口 `/info_open/search`，零 Playwright）→ upsert 入 `policies` 全局表（无 tenant，source_url 去重）→ 正文复用 RAG 流水线 embedding 进全局公开库（`knowledge_base.is_public` + 系统租户 `public`）。`GET /policies` 分页浏览（所有登录用户），前端 `/policies` 页 + 左栏入口。**后台抓取端点 `POST /policies/ingest`（owner/admin）**在 API 进程内跑（复用其 DB/embed 连接，免主机直连远程库的隧道/端口问题）+ 前端「抓取政策」按钮；脚本 `scripts/crawl_wnd_policies.py` 保留（主机直跑因隧道只对容器生效会连不上）。迁移 `e6f7a8b9c0d1`（**现 head**：policies 表 + is_public + 播种 public 租户）。爬虫解析单测 6 + 服务/入库 6；实弹试爬通过。**分支 `feat/public-policy-crawl`（PR #12），2026-06-14 真机验证：迁移已落库、经「抓取政策」按钮入库成功、`/policies` 列表/搜索/详情正常。** 详见 handoff `2026-06-14-public-policy-crawl`。

## 未完成
- 可选：聊天内问政策验证引用、单文件删除端点、上传前端校验、app 日志输出到 stdout。
- 前端认证闭环真机联调；多租户自动化测试。
- 成员管理已实现基础闭环（加/改角色/移除/审批加入申请 + **已登录用户自助申请加入其他组织**，见 handoff `2026-06-15-self-join-org`），尚缺：所有权转移、最后一名 owner 保护的更细规则、"我发起的加入申请"列表。
- **存量重复同名组织清理**（历史 register 产生的同名租户，如两个「重庆理工大学」）待 DB 连通后人工去重；组织名 DB 唯一索引待去重后补。
- **⑥ 资质后续**：能力③ 材料/流程指引（Agent 工具）未做；资质目录除高企外 24 条的 `structured_conditions` 待逐条**校对数值**后补（高企研发费用占比分营收档可建模 banded 条件）。
- 报告生成流水线；GitHub Actions 与分支保护。
- ①b AI 联网补全暂停中，待搜索/企业数据 API 接入后复活。
- 公开库语义检索接入 Agent（KnowledgeBaseTool 纳入 is_public 库）属③范畴。
- **公开政策库多区域**：通用框架已就绪（来源注册表 + 按 source 抓取 + 地区筛选 + 来源选择器，见 handoff `2026-06-15-multi-region-policies`），但仍只有无锡新吴区一个爬虫；新增地区需为其门户单独做爬虫（先确认可逆向抓取，①b 教训）。

## 当前最高优先级

1. **资质目录其余 24 条逐条校对数值后补 `structured_conditions`**（当前仅高企已结构化，差距分析与 A2 指引才更全）；高企研发费用占比分营收档可建模 banded 条件。
2. 公开库语义检索接入 Agent（KnowledgeBaseTool 纳入 is_public 库）：③刻意未做，留作后续小分支；配合 A2 可让 Agent 直接取公开政策原文，是指引体验的天然增强。
3. 报告生成流水线。比赛因走公众号（微信封闭）暂缓。

> ⑥ 能力①②③（A0/A1/A2）均已交付并合并 main，真机走查通过。

## 分支/PR 状态（2026-06-16 收尾）
- `main`：① 企业档案（PR #10）+ ② 公开政策库（PR #12）+ ③ 政策匹配（PR #13）+ ④ 工作台 Feed（PR #16）+ 自助加入其他组织（PR #18）+ 公开政策库通用多区域框架（PR #19）+ ⑥ 资质 Phase 1（PR #21）+ **档案结构化字段 A0 + 资质能力② A1（PR #22）** + **⑥ 能力③ A2 资质指引 Agent 工具（PR #24，真机走查通过）**，均已合并。
- PR #11 `feat/enterprise-profile-enrich`：①b AI 补全，**暂停、暂不合并**（按钮已隐藏；落后 main 多个 PR、已冲突，待复活时一并 rebase 解，见对话记录）。
- `test/c-plus-d`：C+D 集成测试分支（一次性，含暂停的 ①b，**勿合并主干**）。

## 已知风险

- 后端多租户测试覆盖不足，跨租户读取风险未系统验证。
- `.env`（腾讯 COS、`EMBED_API_KEY`）与 `api/config.yaml` 是 Docker 启动前置；含真实机密，保持 gitignored。
- 共享远程数据库依赖每台开发机的一次性 SSH 密钥和 `.env.remote` 配置；不同分支不得并发执行不兼容迁移。
- 检索默认全库，租户库多时为顺序循环，规模大需批量/并发或会话级 scope 收窄。
- 十天范围紧，新增基础设施须直接服务主链路。

## 更新规则

只记录最新事实。任务细节放 GitHub Issue，临时交接放 `handoffs/`，架构原因放 `decisions/`。
