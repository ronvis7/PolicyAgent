# 公开政策库 ②（无锡新吴区政策爬取 + 结构化入库 + 向量双写）

Issue：待创建
分支：`feat/public-policy-crawl`（PR 待创建；迁移未真机执行）
更新时间：2026-06-14

## 目标

主线第②步：以企业为主体的主动情报服务链路 `企业档案 → 公开政策库 → 匹配 → 工作台 Feed`。
本期只做 **爬取 + 结构化入库 + 向量双写**（匹配③/Feed④ 后置）。数据源锁定无锡高新区（新吴区）门户。

## 决策（2026-06-14 与用户敲定）

1. 存储 = **结构化 `policies` 全局表 + 向量双写**（复用 RAG 流水线 embedding 进全局公开库）。
2. 本期范围 = 只做爬取+结构化入库，**不做匹配/Feed**。
3. 触发先用**手动脚本**（定时后置，无调度库）。
4. 数据源先逆向 JSON 接口（成则不依赖 Playwright）。

## 数据源（已逆向，详见记忆 public-policy-source）

- 列表：`POST https://www.wnd.gov.cn/info_open/search`，`siteId=181` + 政策文件 `channelIds=38939,38940,38941,62112,62113,62114` + `pageIndex/pageSize/searchType=2/order=writeTime`。
- 返回 `data.data[]` 直接结构化：`title/indexId(索引号)/organization(发布部门)/effectStatus(效力)/writeTime(日期)/url(详情页,去重键)`；`data.totalPages` 分页。
- 详情页：正文 `div#Zoom`，元数据表 `table.xxgk_table_wza`（文件编号=文号）。
- 合规：robots 仅全禁 GPTBot、禁索引 `/uploadfiles/` 附件 → 普通 UA + 限速 0.8s 爬 HTML，不下载二进制附件。

## 已完成

### 后端
- 域模型 `domain/models/policy.py`（`Policy`，source_url 去重键）。
- 全局表 ORM `infrastructure/models/policy.py`（`policies`，**无 tenant 外键**，source_url 唯一）；仓储协议 + DB 实现（upsert/分页筛选）；UoW 接线（`uow.policy`）。
- 爬虫 `infrastructure/external/crawler/wnd_policy_crawler.py`（httpx+bs4，纯解析 `_parse_list_payload`/`_parse_detail` 与网络分离）。
- 读服务 `application/services/policy_service.py`（分页浏览 + 详情，分页参数 clamp）。
- 入库编排 `application/services/policy_ingest_service.py`（爬→结构化 upsert→向量双写）。**向量双写**：`knowledge_base.is_public` 标志 + 系统租户 `public`（迁移播种）下的固定公开库 `public-policy-kb`，复用 `chunk_pages`+embedding+`document_chunk`；按 source_url 派生确定性 file id 保证幂等。
- 路由 `interfaces/endpoints/policy_routes.py`：`GET /policies`（分页/region/issuer/keyword 筛选）、`GET /policies/{id}`，**所有登录用户可读**；注册到 routes.py；工厂 `get_policy_service`/`get_policy_ingest_service`。
- 迁移 `e6f7a8b9c0d1`（down=`d5e6f7a8b9c0`，**现 head**）：policies 表 + `knowledge_bases.is_public` + 播种系统租户 `public`。纯新增，向后兼容。

### 前端
- `lib/api/policy.ts`（list/get + 类型）；`/policies` 浏览页（搜索/分页/详情 Dialog/原文链接）；左栏「公开政策库」入口。

### 脚本 / 触发
- **后台抓取端点 `POST /policies/ingest?max_pages=N`（owner/admin）**：FastAPI BackgroundTasks 在 API 进程内跑 `PolicyIngestService.ingest`，立即返回。复用 API 自身 DB/embedding 连接，**免去主机直连远程库的隧道/端口问题**（脚本在主机直跑会 connection refused：隧道开在主机 127.0.0.1:本地端口，脚本默认却连容器用的 host.docker.internal）。前端 `/policies` 页 owner/admin 可见「抓取政策」+「刷新」按钮。
- `scripts/crawl_wnd_policies.py --max-pages N`：保留（服务器侧/CI 定时可用；主机手跑需设 `POSTGRES_HOST=127.0.0.1` + 正确本地端口）。

## 验证

- 真机（2026-06-14）：迁移已落库；经「抓取政策」按钮后台入库成功；`/policies` 列表/搜索/翻页/详情正常。

- 服务层 + 爬虫解析单测全绿：新增爬虫解析 6、PolicyService/入库 6；全量单测 **53 passed**（跳过需真库的 status）。
- `py_compile` 全过、`import app.main` 无循环、`alembic heads` 单一 `e6f7a8b9c0d1`。
- **实弹试爬**（无 DB，对真站）：抓 3 条，结构化字段齐全、正文正确抽取（真实政策 1646/5159 字；图解页因正文在 /uploadfiles/ 仅得标题，符合不爬附件预期）。
- 前端 `tsc --noEmit` exit 0、`eslint`（改动文件）exit 0。

## 未完成 / 下一步

- **迁移未真机执行**：需 DB 连通后随 api 启动自动 upgrade 到 `e6f7a8b9c0d1`。
- **真机入库**：`cd api && python ../scripts/crawl_wnd_policies.py --max-pages 2`（需远程隧道/本地库 + `.env` 的 `EMBED_API_KEY`），验证 policies 落库 + 公开库切片。
- UI 联调：`/policies` 列表/搜索/分页/详情。
- 下一步主线：③ 匹配（档案 × 公开政策）→ ④ 工作台 Feed。公开库语义检索接入 Agent（KnowledgeBaseTool 纳入 is_public 库）属③范畴。

## 风险

- 列表/详情接口为站点逆向，源站改版会失效（解析层已与网络分离，便于修）。
- 向量双写挂系统租户 `public`，检索侧（③）需显式纳入 is_public 库，当前 KnowledgeBaseTool 仅按登录租户检索，**尚未**包含公开库。
- 图解/纯图片政策正文为空（附件在 /uploadfiles/ 不爬），属预期；如需正文要另解析附件（受 robots 限制，后置）。
