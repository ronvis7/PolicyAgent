# 公开政策库 —— 通用多区域框架

Issue：待创建
分支：`feat/multi-region-policies`（**PR #19 已合并 main，2026-06-15；分支已删**）
更新时间：2026-06-15

## 背景 / 目标

用户问"公开政策库为什么不能改区域"。排查：区域不是设置项，而是**与"抓哪个门户"绑死**——
`WndPolicyCrawler` 的 `_REGION`/`_BASE` 写死无锡新吴区，抓取端点只挂了这一个爬虫。
本次把"来源/地区"做成**一等可扩展维度**(通用多区域框架)：新增一个地区 = 实现一个爬虫 +
注册一条来源，无需改入库编排/端点。

> 重要：本次是**框架 + 把 WND 接进框架**。库里仍只有无锡数据；要真正看到其他地区，
> 仍需为那个地区的门户**单独做一个爬虫**(同 ①b 教训：先确认门户可逆向抓取再投)。框架/UI 已就绪，
> 加一个地区即"点亮"。

## 已完成（TDD：先写 registry + 按来源 ingest 测试 RED → GREEN）

### 后端
- 来源注册表 `infrastructure/external/crawler/registry.py`：`CrawlerSource(key, name, region, factory)` +
  `CRAWLER_SOURCES`(首版仅 `wnd`) + `list_sources()` + `build_crawlers()`。
- `PolicyIngestService` 改为**按来源选择爬虫**：构造参数 `crawler` → `crawlers: Dict[str, PolicyCrawler]`；
  `ingest(source, max_pages)` 按 source 取爬虫(未知来源 `BadRequestError`)，summary 增加 `source`。
- `get_policy_ingest_service` 用 `build_crawlers()` 注入。
- 端点：`POST /policies/ingest?source=wnd&max_pages=N`(校验 source 合法) + 新增
  `GET /policies/sources`(列出 key/name/region，**注册在 `/{policy_id}` 之前**)。Schema `PolicySourceItem`/`PolicySourceListResponse`。

### 前端
- `policyApi.listSources()` + `policyApi.ingest(source, maxPages)`(源选择)。
- `/policies` 页：① 地区筛选下拉(来自来源地区，传 `region` 给 list)；② 「抓取政策」改为**来源选择下拉**
  (每个来源一项，点击抓该来源)；③ 顶部文案随筛选地区动态显示("各地区/某地区权威政策")。

## 接口
- `GET /policies/sources` → `{items:[{key,name,region}]}`，所有登录用户。
- `POST /policies/ingest?source=&max_pages=` → owner/admin；source 默认 `wnd`，非法报 400。
- `GET /policies?region=...` 地区筛选(既有 ilike 子串筛选，本次前端接上)。
- **无新表、无迁移**。

## 验证
- 单测：新增 `test_policy_ingest_service.py` 3(按来源选择/未知来源报错/注册表)；更新既有 `test_policy_service.py`
  两条 ingest 用例到新签名(`{"wnd": crawler}` + `ingest("wnd", ...)` + summary 含 source)。全量 **82 passed**，仅 status 1 error(需真库)。
- `import app.main` OK；`/policies/sources` 在 `/{policy_id}` 之前。
- 前端 `tsc`/`eslint` 绿。

## 未完成 / 下一步
- **真正的第二个地区**：需为目标门户(如重庆)做爬虫并注册。先调研其门户能否像 wnd 那样逆向 JSON 接口；
  能则加 `CqPolicyCrawler` + 一条 `CrawlerSource` 即可，前端零改动自动出现在来源/地区下拉。
- 可选：来源元数据(更新时间、最近抓取条数)展示。

## 风险
- 框架就绪但数据仍单一(无锡)：地区筛选下拉当前只有一个地区，符合预期。
- 各地门户结构各异、反爬程度不一，逐个评估可抓性，勿假设都能逆向(①b 教训)。
