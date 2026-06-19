# 当前状态

最后更新：2026-06-19（晚，PR #52 数据来源 + #53 资质 banded + #54 工信厅 gxt 申报源 + #55 gxt 政策文件栏目）

## 仓库状态

- 主仓库：`policy_manus`，当前分支 `main`（干净，已同步 origin）。
- `main` 已合入 ②公开政策库（PR #12）+ ③政策匹配（PR #13）+ ④工作台 Feed（PR #16）+ 自助加入其他组织（PR #18）+ 公开政策库通用多区域框架（PR #19）+ ⑥资质 Phase 1（PR #21）+ 企业档案结构化字段 A0 + 资质能力②差距分析 A1（PR #22）+ ⑤申报截止跟踪+主动提醒+`wnd-apply` 爬虫源（**PR #32，已合并**）+ 公开政策定时重爬（**PR #34，已合并**）+ 前端视觉统一+品牌收尾（PR #35，2026-06-17 合并）+ 企业档案查看态打磨 + 上海杨浦区政策来源 + 抓取反馈（PR #37，2026-06-17 合并）+ 注册引导/个人工作区提示 + 工作台政策资质分栏 + 政策库默认地区（PR #39，2026-06-17 合并）+ ADR 003 私有政策库双轨 Embedding **阶段 A 租户级 Embedding BYO key（PR #42）+ 阶段 B Agent 去公开库 + 私有政策库收藏（PR #43）** + **文件下载/预览 401 鉴权修复（PR #44）+ 私有政策库收尾·批量收藏 + 知识库真实文件数（PR #45）**（均 2026-06-18 合并）+ 跨租户隔离 endpoint 测试进 CI（PR #46）+ **政策匹配简报 PDF 一键导出（主线尾巴，PR #47）+ 结构化匹配质量提升（jieba 分词+饱和归一+地区加成，PR #48）+ DB-in-CI 仓储 SQL 层隔离集成测试（PR #49）+ 企业档案关键词智能提取（PR #50）+ 结构化匹配自动从主营业务挖词（真机走查修，PR #51）+ 数据来源透明中心（政策源溯源 + 资质目录来源，PR #52）**（均 2026-06-19 合并）。
- **基建：共享 PostgreSQL 已从 `118.196.142.223`（停机）迁到 `118.196.142.222`**（部署/数据/备份逐项校验 + 全栈 Remote 真机走查通过，详见 handoff `2026-06-16-postgres-server-migration`）。

## 已完成

> 细节以 `git log` 为准，本节只记里程碑。

- **多区域申报源·江苏省工信厅门户（gxt，PR #54，2026-06-19 合并，真机 1 页冒烟通过）**：#3 多区域申报源扩省级覆盖。**先做可逆向性甄别**（①b 教训）：科技厅 `kjt` 被 WAF 稳定挡死（TLS WinError 10053/HTTP 502，放弃）；工信厅 `gxt` 可访问，「文件通知」栏目正是省级项目申报通知主阵地（创新型中小企业评价/专精特新/制造业），与资质目录工信类契合。门户为**大汉版通(Hanweb)CMS**：列表走 `GET /module/web/jpage/dataproxy.jsp`（columnid/webid/unitid/appid/col 定位 + startrecord/endrecord/perpage 翻页），返回 XML `<totalrecord>` + 每条 `<record><![CDATA[<li><a href title>标题</a><span>日期</span></li>]]>`，最新优先；详情静态 HTML 正文在 `div.article_zoom`（回退 `.nscont`/`#con1`），文件通知多无文号表故文号尽力而为。`GxtPolicyCrawler`（纯解析+网络分离、限速容错、column_id/title_keyword 可配）+ registry 注册 `gxt`（江苏省，home_url）+ `POLICY_RECRAWL_SOURCES` 追加 gxt。**入库编排/端点/前端零改动自动出现**。11 单测、离线 253 passed、真机 1 页抓 19 条正文全非空。零迁移、零新增依赖。**续：PR #55 加 `gxt-policy`（政策文件栏目 col80179）**——同站不同 jpage 实例(unitid 参数化)、详情正文在 `#Zoom`(兼容两套模板)、列表日期在 `<b readlabel>`(加 URL 路径派生日期兜底)、文号收紧只认真文号形态(杜绝索引码误收)；政策文件无截止故不入重爬。真机冒烟 16 条全有日期、真文号 13/16。
- **资质 banded 分档条件模型（PR #53，2026-06-19 合并）**：⑥ 能力② 扩展——支持门槛随另一指标落档而变的分档硬条件。`ConditionBand`（单档 max_value 上限 + threshold，None=开口顶档）+ `BandedCondition`（被核验指标 metric + 落档指标 band_metric + 升序 bands），`Qualification` 加 `banded_conditions`。gap 内核 `_resolve_band` 选档 + `_evaluate_banded` 先定档再比指标，**band_metric 或被核验指标任一缺失→待确认**（不误报不达标），banded label 一并从 manual_review 去重。高企「研发费用占销售收入比例」接入为首个真实 banded 条件（按营收三档 ≤5000万→5%/5000万~2亿→4%/>2亿→3%，数值=现行办法概要待业务方核对）。**前端零改动**（banded 产出标准 ConditionCheck，detail 携带落档上下文，沿用 `qualification-detail.tsx` 渲染）。零迁移、零新增依赖，新增 7 单测、离线 242 passed、CI 三项全绿。**扩更多资质**：逐条配条件 + 业务方核对数值；行业分档需先扩"行业档"落档指标。
- **数据来源透明中心（政策源溯源 + 资质目录来源，PR #52，2026-06-19 合并，真机走查通过）**：建立数据来源透明度——让用户看到政策/资质信息来自哪些权威源头（"数据来自政府官网、不是瞎编"的信任感）。**零迁移、只读聚合**：`CrawlerSource` 加 `home_url`（wnd/wnd-apply/shyp 官网）；仓储 `stats_by_source()` 单条 `GROUP BY source` 聚合各源条数 + 最近抓取时间（无 N+1，DB/内存 fake 双实现）；`PolicyService.list_sources_with_stats()` 合并注册表与统计（无政策源回落 0/None）；`GET /policies/sources` 增量返回 `home_url`/`policy_count`/`last_crawled_at`（向后兼容）；`GET /qualifications/catalog`（注册在 `/{key}` 前）返回**全量**资质目录来源（发证机关/政策依据/末次核对/免责），**不依赖租户档案、不做匹配过滤**，复用既有 `service.list_catalog()`。前端新页 `/sources`「数据来源」（政策源卡片=官网外链+收录条数+最近更新；资质来源按级别分组+全局免责）+ 左栏入口。**刻意不做**「用户粘贴任意网址实时爬取」——撞 ①b 教训（无可靠通用数据源），留作"来源建议众包"另议。新增单测 service 合并/catalog 非租户过滤 + 集成 `stats_by_source` 真库 GROUP BY；CI 三项（含 integration 真库）全绿；离线 235 passed。
- **政策匹配简报 PDF 一键导出（主线尾巴，PR #47，2026-06-19 合并）**：产品主线"企业档案→公开政策库→匹配→Feed→接问 AI/报告"的最后一步。不做重报告流水线（价值存疑），改轻量交付物：把企业画像 + ③匹配政策 + ⑥资质差距 + ⑤临期申报组装为 PDF。`ReportService.build_brief`(复用档案/Feed/资质服务，Top15 政策按分降序剔除已忽略 / Top8 资质差距 / 30 天临期) + `infrastructure/report/pdf_renderer.py`(reportlab 纯函数，内置 `STSong-Light` 中文字体、无系统原生依赖；差距/截止带免责声明；XML 特殊字符转义) + `GET /reports/policy-brief`(application/pdf，限当前租户)；前端 `/feed` 顶部「导出简报」按钮(复用 PR #44 带 Bearer 鉴权下载)。**收尾**：政策表「匹配分」列误用原始 RRF 分(受 k=60 压制天然 0.02 上下、几乎同值)，改为展示命中度%/语义相似度，与网页卡片口径一致、RRF 仅用于排序。新增依赖 `reportlab`。13 单测、零迁移。
- **结构化匹配质量提升（jieba 分词 + 饱和归一 + 地区加成，PR #48，2026-06-19 合并）**：导出简报后发现命中度普遍偏低/为 0，定位 `policy_matcher.py::score_terms` 三根因并一并修：①纯子串匹配脆 → 引入 **jieba** 标题按 token 重合判命中(保留原样子串)，正文仍走子串控成本；②归一化稀释(旧按全部档案词数归一、填得越全分越低) → 改饱和归一 `weight/(weight+2)`，不被未命中词稀释；③地区未进分 → 内容已命中时叠加 +0.15 地区加成(无内容命中不单独刷分)。加停用词降噪。纯函数内核，新增依赖 `jieba`，零迁移。
- **结构化匹配自动从主营业务挖词（PR #51，2026-06-19 合并，真机走查发现并修）**：#48/#50 上线后真机走查命中度仍**全 0**、语义正常(0.5-0.6)——根因是两路输入不一致：语义路 `build_profile_query` 吃主营业务，结构化路 `extract_profile_terms` 只认 关键词/技术域/资质/行业 标签；用户实际只填了主营业务、标签全空，故结构化无词可命中。修：`extract_profile_terms` 在显式标签外，再用 jieba(复用 `keyword_extractor`)从 `main_business` 自动挖至多 8 词并入(显式标签优先、去重)，两路对齐同一输入；配合 #48 饱和归一不稀释。纯函数、零迁移、零新增依赖。
- **DB-in-CI 仓储 SQL 层隔离集成测试（PR #49，2026-06-19 合并）**：补上内存隔离套件测不到的那层——仓储 SQL 的 tenant WHERE 真实生效。`tests/integration/` 连真 Postgres+pgvector，跑 `alembic upgrade head`(连带验证迁移链) + 真 `DBUnitOfWork`/真仓储，断言 session/knowledge_base/enterprise_profile/feed 的 get/list/delete 均"跨租户取不到·不生效 + 本租户成功"。仅 `RUN_DB_TESTS=1` 运行、否则按路径精确 skip；CI 新增 `integration` job（`pgvector/pgvector:pg16` service 容器）。**仍可续加**：membership 横向越权、tenant_settings(LLM/embed key) 读取、document_chunk。
- **企业档案关键词智能提取（PR #50，2026-06-19 合并）**：匹配命中度低的"数据侧"那一半——帮用户从自己的主营业务/行业自述一键提取候选关键词补全(建议词取自企业描述，最可能也出现在相关政策里)。纯函数 `keyword_extractor.suggest_keywords`(jieba TF-IDF + 停用词/已填项过滤，复用 jieba) + `POST /enterprise-profile/keyword-suggestions`(无状态)；前端档案编辑「✨ 智能提取关键词」按钮，结果作关键词字段 presets 一键入列。9 单测、零迁移。
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
- **企业档案查看态打磨 + 上海杨浦区政策来源 + 抓取反馈——已合并（PR #37）**：本轮为现有功能打磨 + 点亮一个新地区，不加新功能。**①企业档案页**重写为查看/编辑分态：默认进"企业名片"查看态（Hero 卡 + 档案完整度进度条 + 资质/领域标签云 + 经营研发指标数据卡，未填弱化"未填写"区分≠0），owner/admin 点「编辑」切表单态（绑 draft，取消放弃/保存切回），member 只读、空档案有引导页；纯前端无接口/迁移。**②上海杨浦区来源**按既有多区域框架点亮一个新地区：逆向 `www.shyp.gov.cn`（东网政务云 CMS，列表 `POST /front/api/data/search` + `channelList:["1899"]` 数组才生效、详情静态 HTML `#ivs_content`），新增 `ShypPolicyCrawler` + `registry.py` 注册 `shyp/上海市杨浦区`，入库编排/端点/前端**零改动**自动出现该地区；已把 `shyp` 追加进 `POLICY_RECRAWL_SOURCES` 默认值（`wnd-apply,shyp`），随无锡 04:00 一同定时重爬保鲜。**③公开政策库抓取反馈**：抓取是 fire-and-forget 后台任务（约 1-2 分钟），原前端 POST 返回即停 loading 像"秒完成"、无完成信号；改为抓取中保持按钮 loading+"抓取中…"+顶部横幅，固定 90s 窗口后自动刷新列表+toast 收尾。9 解析单测 + **全量 182 passed**（唯一 error 为既有需真库的 `test_get_status`），**真机实跑验证**：连 .222 抓取杨浦区入库成功，列表/地区筛选/正文/文号/索引号解析正确。无表无迁移（`alembic head` 不变），CI backend+frontend 双绿，**PR #37 已合并 main（2026-06-17）**。详见 handoff `2026-06-17-profile-view-and-yangpu-source`。**遗留观察项**：杨浦区"政府文件"含部分非惠企公文（请示/统计法转载等），先上线观察，有噪音再在 catalog/匹配侧做聚焦过滤。
- **端到端走查发现的体验打磨——已合并（PR #39）**：一次完整用户旅程走查（注册→建档→抓政策→Feed→资质→Agent→隔离）中由用户反馈、即修。**#1 注册/工作区**：「加入已有组织」语义是"申请加入他人组织、待管理员批准"，批准前落进临时个人工作区；单人给自己公司建工作区者误选 join 后困在空工作区。注册页模式切换下加**场景化说明**（create=自己首次建；join=同事已建、需审批、批准前临时个人工作区），join 成功 toast 点明；`TenantInfo`+前端 `AuthTenant` 透出 `is_personal`（领域模型本就有）；app-shell 在个人工作区时顶部显**可关闭提示横幅**。**这是隔离正常工作的表现（join 用户被正确隔离、看不到目标组织数据），非泄漏，修的是引导/可见性**。**#4 工作台布局+地区**：Feed 顶部加机会类型分栏（全部/政策机会/资质机会）前端按 type 分流，政策资质不再混列表；公开政策库首挂载按企业所在地（区/县名含、回退市名）预选地区、手动切后不覆盖；资质页本就按档案匹配（含地区门槛）无下拉、不动。**#3 抓取"没生效"实为去重**：日志确认重抓只 UPDATE 已存在政策（按 source_url 去重），列表条数不变才像没生效，功能正常。纯前端为主（仅 `is_personal` 一处后端透出），无表无迁移，CI 双绿，真机重建栈 api/ui healthy、网关 200。**待续走查**：#5 资质差距分析、#6 Agent 问答 RAG、#7 跨租户隔离（#1 已侧面验证隔离正常，未专门双账号对撞）。详见 handoff `2026-06-17-walkthrough-onboarding-layout`。
- **前端 UI 刷新（进行中分支 `feat/policy-ui-refresh`）**：按 `preview.html`、研究报告、FiscalNote 参考和用户补充的知识库参考图，把左侧 IA、公开政策库、知识库页刷新为中文企业政策工作台风格；公开政策库仍只接现有 `/policies`、`/policies/sources`、`/policies/ingest`。知识库已改为“文档知识库”卡片首页 + 新建知识库大弹窗 + 详情页“文件表格/Source-MD 预览”默认布局，并保留 Neo4j 风格图谱预留入口；**无后端文件夹字段/无原文预览接口/无真实 Neo4j/无接口变化**。`docker compose build policy-ui`、改动文件 eslint、`git diff --check` 通过；Docker 重启 `policy-ui` healthy，登录当前用户走查 `/knowledge`、`/knowledge/demo-kb-policy-materials`、图谱切换通过。全量 lint 仍受既有未改文件影响。详见 handoff `2026-06-16-policy-ui-refresh`。
- **工作台 Feed ④（物化政策信息流 + 未读红点）——已交付**：主线第④步。在 ③ 即时匹配之上物化 `policy_matches` 表（`UNIQUE(tenant_id, policy_id)`，计算快照落列免 N+1，状态机 unread/read/applied/ignored，**含 `type` 列为 ⑥ 资质/比赛预留**）。`FeedService.recompute_for_tenant`：新增→unread（驱动红点）、已存在只更新快照保留用户 status/created_at、跌出候选保留不删。**触发 (a) 抓取政策入库后 + (b) 改企业档案后**在端点排后台任务重算当前租户，(c) Feed 页「重新匹配」手动兜跨租户。端点 `/feed`（list/unread-count/recompute/mark-read/{id}/status，所有登录用户限当前租户）。前端 `/feed` 工作台页（状态筛选/重新匹配/已申报·忽略/详情弹窗复用 `/policies/{id}`）+ 左栏「工作台」入口未读红点（自定义事件 `feed:unread-changed` 同步）；**删除 `/matches` 页与「政策匹配」入口**。运维：`policy-api` healthcheck `start_period` 20s→120s（远程库冷启动不再被误判 unhealthy）。迁移 `f7a8b9c0d1e2`（**现 head**，纯新增表 + tenant_id/status 索引）。单测 FeedService 7 + 全量 **74 passed**；tsc/eslint 绿。**PR #16 已合并 main（2026-06-15），迁移已真机执行（远程库 `alembic current=f7a8b9c0d1e2`、`policy_matches` 表已建）、Docker 全栈健康。** 详见 handoff `2026-06-15-feed-impl`。
- **政策匹配 ③（企业档案 × 公开政策）——本期交付**：主线第③步。即时计算、不落表：按当前租户企业档案现算可申报政策候选。**两路融合**：①结构化命中（档案 `keywords/tech_domains/qualifications/industry` 词表落在政策 `title`(权重高)+`body_text`，归一化命中度 + 命中词）；②语义召回（档案画像 `industry+main_business+tech_domains+keywords` 拼查询 → embedding → 检索公开库 `public-policy-kb`/系统租户 `public` → 切片按 `source_url` 聚合回政策）；两路有序候选经 **RRF**（k=60）融合排序，输出带「推荐理由」（命中关键词/地区匹配/语义相关度）。纯函数内核 `domain/services/policy_matcher.py`（`extract_profile_terms`/`build_profile_query`/`region_matches`/`score_terms`/`structured_score`/`reciprocal_rank_fusion`）+ 应用服务 `policy_match_service.py`；端点 `GET /policies/match?top_k=N`（所有登录用户，限当前租户档案，**注册在 `/{policy_id}` 之前**避免被路径参数捕获）；仓储加 `list_candidates`/`list_by_source_urls`（语义回查批量 IN，无 N+1）。前端 `/matches` 候选页（分数/命中度/语义分/推荐理由/详情弹窗复用 `/policies/{id}`）+ 左栏「政策匹配」入口。**无新表、无迁移**（`alembic heads` 仍 `e6f7a8b9c0d1`）。单测：匹配器纯函数 10 + 服务 4，全量 **67 passed**（跳过需真库的 status）；`import app.main` OK；前端 tsc/eslint 绿。**决策**：即时计算（物化留作④Feed）、本期不含 Agent 接公开库（KnowledgeBaseTool 纳入 is_public 留作后续小分支）。**PR #13 已合并 main（2026-06-15），Docker 起栈连远程库 `/matches` 走查通过。** 详见 handoff `2026-06-15-policy-matching`。
- **政策申报截止跟踪 + 主动提醒 ⑤（LLM 抽取 + 临期 Feed）——本期交付**：把「主动情报」落到官网申报
  互补的一层——「申报还有 N 天截止」。截止日期源站无结构化字段、只埋正文，故 **LLM 抽取 + "待核对"纪律**
  (抽不到标 unknown/绝不编造，抽到带原文窗口+免责，沿用资质 A1/A2 风险纪律)。`Policy` 加
  `apply_deadline`/`apply_window_text`/`deadline_status`；`deadline_extractor.py`(纯函数 prompt/解析 + LLM 封装，
  异常一律回退 unknown)；`PolicyIngestService` 注入平台默认 LLM 逐篇 best-effort 抽取(无 key/失败不阻断入库)。
  **提醒复用 Feed、零提醒表**：截止快照落 `policy_matches`，`GET /feed/expiring?within_days=14`(仅 extracted
  未 ignored，按截止升序)，`days_left` 读取侧派生；前端 Feed 临期徽章(≤3天红/≤14天琥珀/过期/常年) +
  政策详情截止区块+免责。**关键转折**：原「政策文件」栏目结构上不带申报截止(实抽 0/40)，遂扩 wnd 爬虫
  支持**按标题关键词全站检索**(逆向确认 `/info_open/search` 的 `title` 字段过滤标题)，新增来源 `wnd-apply`
  (项目申报通知)。迁移 `a8b9c0d1e2f3`(**现 head**，纯新增列+索引)。新增单测 deadline_extractor 13 +
  ingest 截止 3 + feed 临期 4 + 爬虫申报模式 3，全量 **169 passed**；tsc/eslint 绿。**分支
  `feat/policy-apply-deadline`（PR 待开）；全栈 Remote 真机走查通过**(连 .222：迁移自动落库；
  `ingest('wnd-apply')` 60 篇 → **extracted 23**，抽取真实且处理窗口末/隐含年份/延长/多档取最终，
  37 unknown 为附件 PDF/结果公示正确降级；申报通知数据已保留)。详见 handoff `2026-06-17-policy-apply-deadline`。
- **公开政策库 ②（爬取+结构化入库+向量双写）**：主线第②步。爬无锡新吴区门户「政策文件」栏目（逆向 JSON 接口 `/info_open/search`，零 Playwright）→ upsert 入 `policies` 全局表（无 tenant，source_url 去重）→ 正文复用 RAG 流水线 embedding 进全局公开库（`knowledge_base.is_public` + 系统租户 `public`）。`GET /policies` 分页浏览（所有登录用户），前端 `/policies` 页 + 左栏入口。**后台抓取端点 `POST /policies/ingest`（owner/admin）**在 API 进程内跑（复用其 DB/embed 连接，免主机直连远程库的隧道/端口问题）+ 前端「抓取政策」按钮；脚本 `scripts/crawl_wnd_policies.py` 保留（主机直跑因隧道只对容器生效会连不上）。迁移 `e6f7a8b9c0d1`（**现 head**：policies 表 + is_public + 播种 public 租户）。爬虫解析单测 6 + 服务/入库 6；实弹试爬通过。**分支 `feat/public-policy-crawl`（PR #12），2026-06-14 真机验证：迁移已落库、经「抓取政策」按钮入库成功、`/policies` 列表/搜索/详情正常。** 详见 handoff `2026-06-14-public-policy-crawl`。

## 未完成
- 可选：聊天内问政策验证引用、单文件删除端点、上传前端校验、app 日志输出到 stdout。
- 前端认证闭环真机联调；多租户自动化测试。
- 成员管理已实现基础闭环（加/改角色/移除/审批加入申请 + **已登录用户自助申请加入其他组织**，见 handoff `2026-06-15-self-join-org`），尚缺：所有权转移、最后一名 owner 保护的更细规则、"我发起的加入申请"列表。
- **存量重复同名组织清理**（历史 register 产生的同名租户，如两个「重庆理工大学」）待 DB 连通后人工去重；组织名 DB 唯一索引待去重后补。
- **⑥ 资质后续**：目录结构化条件已逐条 triage（PR #26）：`high-tech-enterprise` + `tech-sme`（职工≤500/营收≤2亿 LTE）可结构化。**banded（分档）条件模型已就绪（PR #53）**——支持门槛随营收/行业等落档而变，高企「研发费用占比」已接入为首个 banded 条件（按营收三档）。要再扩：为其余资质逐条配 `banded_conditions`/`structured_conditions`，**数值须业务方按当年官方办法核对**；行业分档需新增"行业档"落档指标（当前 band_metric 仅营收/规模类数值字段）。
- 报告生成流水线；GitHub Actions 与分支保护。
- ①b AI 联网补全暂停中，待搜索/企业数据 API 接入后复活。
- **公开政策库多区域**：通用框架已就绪（来源注册表 + 按 source 抓取 + 地区筛选 + 来源选择器，见 handoff `2026-06-15-multi-region-policies`）。现有来源：无锡新吴区（`wnd`/`wnd-apply`）+ **上海杨浦区（`shyp`，PR #37）** + **江苏省工信厅（大汉 CMS dataproxy 逆向，真机 1 页冒烟通过、真机走查待做）：`gxt`=文件通知/含项目申报(PR #54)、`gxt-policy`=政策文件/规范性文件(PR #55)**。再扩地区仍需为其门户单独逆向做爬虫（先确认可逆向抓取，①b 教训：科技厅 `kjt` 已甄别被 WAF 挡死、放弃）。

## 当前最高优先级

**产品主线已贯通并收口**：企业档案①→公开政策库②→匹配③→工作台 Feed④→申报截止⑤→资质⑥→
私有政策库(ADR003 阶段 A+B)→**报告(主线尾巴，PR #47)**，每步均合并 main。本轮(2026-06-19)
四连击：报告 PDF 导出(#47) + 匹配质量(算法侧 #48 + 数据侧关键词 #50) + DB-in-CI 隔离(#49)；
随后补**数据来源透明中心(PR #52，真机走查通过)**。**下一步无单一最高优先级**，按需从下列选。
唯一已合并未真机走查项：**#47 报告 PDF 导出**（其余均已真机验证）。

> 待办候选（无强先后）：
1. **真机走查收尾**：#47 报告导出真机走查待做；匹配命中度——首轮走查发现仍全 0（根因=只填主营业务、标签空），#51 修复后**真机已验证通过**（2026-06-19 重建栈+重新匹配，只填主营业务的档案出现非零命中度，实测有 50% 命中项）。命中度高低进一步取决于档案完善度（标签/主营业务越全越准），属正常预期。
2. **多区域申报源**：已扩江苏省工信厅 `gxt`(文件通知, PR #54) + `gxt-policy`(政策文件, PR #55)；
   ⑤临期提醒 + 定时重爬（含 gxt）已就绪。再扩覆盖需各门户单独逆向、`POLICY_RECRAWL_SOURCES`
   追加 key、`registry.py` 一并填 `home_url`（PR #52 起「数据来源」页自动展示）。**已甄别失败**：
   科技厅 `kjt` 被 WAF 挡死，勿再试。可后续按 `title_keyword='申报'` 派生更聚焦的申报子源，
   或逆向其他已探活省厅(财政厅 `czt` 已确认可访问)。
3. **续加隔离自动化**：membership 横向越权 / 租户 LLM·embed key 读取 / 会话子资源 / document_chunk，
   按 `tests/app/isolation/`(内存) 或 `tests/integration/`(真库) 模式补。
4. 报告**已交付为轻量 PDF**(PR #47，非重流水线)；比赛因走公众号（微信封闭）暂缓。
5. **让更多资质可结构化差距分析**：banded 条件模型已就绪（PR #53，高企研发费用占比已接入）；扩更多资质=逐条配 `banded_conditions`/`structured_conditions` + **业务方核对当年数值**；行业分档需先扩"行业档"落档指标。

> ⑥ 能力①②③（A0/A1/A2）均已交付并合并 main、真机走查通过；目录结构化条件已 triage（PR #26）。
> 公开库语义检索已接入 Agent（PR #28，KnowledgeBaseTool 默认范围=私有库+全局公开库）、真机走查通过。
> **真机修复**：发现 ②向量双写因外键 flush 顺序 bug 一直静默回滚致公开库切片为 0，已修（PR #29）；重跑 ②入库后 .222 公开库已落 154 切片/40 文件，Agent 可检索公开政策原文。
> **⑤ 申报截止跟踪 + 主动提醒**已交付（LLM 抽取 + 临期 Feed + 新增 `wnd-apply` 项目申报通知爬虫源）、真机走查通过（申报通知实抽 extracted 23/60）。**PR #32 已合并 main**。
> **定时重爬**：应用内 APScheduler 调度器每天 04:00 CST 重爬 `wnd-apply` 保鲜（env 全可调），真机验证 job 注册/next_run 正确。**PR #34 已合并 main**。详见 handoff `2026-06-17-scheduled-apply-recrawl`。
> **前端视觉统一 + 品牌收尾（PR #35，已合并）**：采纳同事 `ui` 分支（政策库/知识库页刷新，知识库 Neo4j 图谱/文件夹/KB 类型卡等预留功能保留作路线图展示），把工作台 Feed/资质/企业档案/登录注册拉齐到同一套视觉语言；修复企业档案分区标题(legend 跳出 fieldset padding)；品牌收尾（落地页问候改真实 display_name、logo 占位与助手字标统一 PolicyManus、推荐问题换成贴合产品文案）。纯前端、无接口/迁移。详见 handoff `2026-06-17-ui-refresh-and-brand`。

## 分支/PR 状态（2026-06-19 收尾）
- `main`：①~⑥ 主线 + 私有政策库(ADR003 A+B, PR #42/#43) + 文件下载 401 修复(#44) + 私有库收尾(#45)
  + 跨租户隔离 endpoint 测试进 CI(#46) + **报告 PDF 导出(#47)** + **匹配质量 jieba(#48)** +
  **DB-in-CI 隔离集成测试(#49)** + **档案关键词智能提取(#50)** + **结构化挖主营业务词(真机走查修, #51)**
  + **数据来源透明中心(#52)** + **资质 banded 分档条件(#53)** + **江苏省工信厅 gxt 申报源(#54)** + **gxt 政策文件栏目 gxt-policy(#55)**，均已合并；命中度修复(#51)、数据来源页(#52)真机已验证通过，#47 报告导出 + #53 banded + #54/#55 gxt 真机走查待做。
- PR #11 `feat/enterprise-profile-enrich`：①b AI 补全，**暂停、暂不合并**（按钮已隐藏；落后 main 多个 PR、已冲突，待复活时一并 rebase 解）。
- `test/c-plus-d`：C+D 集成测试分支（一次性，含暂停的 ①b，**勿合并主干**）。
- 工作区未跟踪 `docker-compose.server.yml`：服务器本机部署 override（接 `/opt/policy-postgres`），按用户意图暂不提交、暂不碰服务器部署。
- 新增依赖（本轮）：`reportlab`（PDF）、`jieba`（中文分词，匹配+关键词共用）；均已入 `pyproject`/`requirements`/`uv.lock`。

## 已知风险

- 跨租户隔离：① 手动对撞探针 `scripts/cross-tenant-probe.ps1`（18 项，连真实栈）；② **自动化 endpoint 隔离测试已进 CI**（PR #46，`api/tests/app/isolation/`，9 项：会话/知识库读删、企业档案不串、**Feed 改状态**、**文件下载**、无/坏令牌→401，均"跨租户→404 + 本租户→成功"双向断言；TestClient + 依赖覆盖 + 内存仓储，不连库）。CI backend job 已从只跑 `tests/app/domain` 扩为跑全部离线测试（忽略需真库的 `test_get_status`），**233 passed + 4 skipped**（含集成套件，未启用真库时 skip）。③ **仓储 SQL 层 WHERE 隔离回归已进 CI**（**PR #49**，`tests/integration/`，连真 Postgres+pgvector + alembic + 真仓储，覆盖 session/knowledge_base/enterprise_profile/feed 的 get/list/delete 跨租户双向断言；`RUN_DB_TESTS=1` 触发、CI `integration` job 起 service 容器）。**仍未自动化**：成员 `membership_id` 横向越权、租户 LLM/embed key 读取、会话 chat/stop/bind-kb、document_chunk（可按隔离套件/集成套件模式续加）。详见 handoff `2026-06-18-cross-tenant-isolation-probe` / `-cross-tenant-isolation-ci`。
- `.env`（腾讯 COS、`EMBED_API_KEY`）与 `api/config.yaml` 是 Docker 启动前置；含真实机密，保持 gitignored。
- 共享远程数据库依赖每台开发机的一次性 SSH 密钥和 `.env.remote` 配置；不同分支不得并发执行不兼容迁移。
- 检索默认全库，租户库多时为顺序循环，规模大需批量/并发或会话级 scope 收窄。
- 十天范围紧，新增基础设施须直接服务主链路。

## 更新规则

只记录最新事实。任务细节放 GitHub Issue，临时交接放 `handoffs/`，架构原因放 `decisions/`。
