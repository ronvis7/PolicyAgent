# 赛事体验打磨（工作台地区聚合 + 手动抓取 + 飞书交互卡片 + 抓取时间修复 + 常设赛区）

Issue：—
分支：`feat/contest-region-view`(PR #74) / `feat/feishu-interactive-card`(PR #75) /
`fix/source-last-crawled-zero-result`(PR #76) / `feat/curated-contest-regions-sh-wh`(PR #77)
——**四个 PR 均已合并 main**（`d55337d`/`673ae55`/`05a6160`/`c99bff2`）
负责人：—
更新时间：2026-07-09

## 目标

用户反馈"前端赛事这块自由度太低"，本轮针对性打磨：赛事按地区聚合、可手动抓取、数据来源
分区、飞书推送升级为交互卡片；顺手修"抓 0 条时最近更新一直显示尚未抓取"；并按用户要求
加上海/武汉赛区。**均未部署 .222**（用户明确：dev 阶段，测试上线阶段才全量部署）。

## 已完成

### A. 工作台赛事地区聚合两级视图 + 数据来源赛事分区可手动抓取（PR #74，纯前端）

- **工作台「赛事机会」→ 两级视图**（`ui/src/app/feed/page.tsx`）：第一级按参赛地区聚合的
  卡片网格（📍地区名 + "N 个可参加比赛"，数量降序），点卡片下钻到该地区比赛列表，「← 全部
  地区」面包屑返回。复用 `FeedItem.region`，切换机会类型 tab 时重置下钻状态。
- **数据来源页拆「赛事数据来源」分区**（`ui/src/app/sources/page.tsx`）：按 `item_type` 拆
  政策/赛事两区；赛事源对 **owner/admin** 出「抓取」按钮（二次确认弹窗，明示写共享库 + 向
  已配飞书组织推送），复用 `POST /policies/ingest`，90s 窗口后自动刷新收录统计。抽出共用
  `SourceCard` 组件。
- **闭环**：数据来源页抓 cnmaker → 入库后工作台长出深圳/云南等地区卡片、档案参赛地区选项自动出现。

### B. 飞书新赛事推送升级为交互卡片（PR #75，纯后端）

- `build_contest_message` 从 `post` 富文本 → `interactive` 交互卡片
  （`api/app/infrastructure/external/notify/feishu_webhook.py`）：
  - **卡片头临期变色**：按批次最紧迫报名截止 ≤3 天红 / ≤14 天橙 / 否则蓝（与 Feed 徽章口径一致）。
  - **每条一块**：加粗可点标题(原文链接) + 📍地区 + ⏰报名截止倒计时("还剩 N 天"，⑤抽取到才有；
    未抽到回落发布日期)。
  - **按钮**：配 `WEB_BASE_URL` 时底部「打开工作台查看全部」直达 `/feed`。
  - note 声明"报名信息以官方原文为准 · 来源 X · 依你的参赛关注地区筛选"。
- 新增 `WEB_BASE_URL` env（`api/core/config.py`；留空不出跳转按钮、不影响推送）；两个 push
  hook + `service_dependencies` 透传。租户扇出/关注地区过滤/上限10/best-effort 全部照旧。
- **待人工确认**：飞书卡片真机渲染（lark_md 链接 + header 配色）需在真实群眼看一次。

### C. 数据来源"最近更新"——抓 0 条也记录运行时刻（PR #76，后端 + 新表）

- 根因：`最近更新` 取 `MAX(policies.crawled_at)`，抓到 0 条(全被保鲜过滤/门户无匹配大赛)时
  无政策行被写、时间戳不动 → 一直"尚未抓取"。
- 修复：新增 **`source_crawl_states` 表**（迁移 `f3a4b5c6d7e8`，**现 head**，纯新增表：source 主键
  + last_crawled_at + last_new_count + last_crawled_count）；`PolicyRepository` 加
  `record_crawl`/`crawl_run_times`（DB + 内存 fake 双实现）；`PolicyIngestService.ingest` 完成后
  记录本次运行（即使 0 条）；`list_sources_with_stats` "最近更新"优先取运行记录、回落
  `MAX(crawled_at)`（向后兼容）。前端零改动。也让 04:00 定时重抓的来源时间如实刷新。

### D. 参赛关注地区并入常设赛区（上海/武汉）（PR #77，纯后端）

- **实地探查结论**：上海/武汉当前**无可靠自动数据源**——cnmaker 官网首页当季未主推(22 条静态
  列表无上海/武汉)、动态全量接口(`findactivices.xml`/`getCompeNews2.xml`)被 SiteBuilder 令牌
  网关挡住(直连 GET/POST 均 302 回 default.htm、脆弱)、政府门户无当季赛事栏目。硬爬需
  Playwright(重/脆/破坏"零 Playwright"设计)或逆向令牌流(脆弱)，不值当。
- 方案：「参赛关注地区」本质是关注偏好，改为 **数据驱动 ∪ 常设赛区**。新增
  `CURATED_CONTEST_REGIONS=("上海市","湖北省武汉市")`（`registry.py`，region 串与
  `CnmakerContestCrawler.map_region` 输出一致——map_region 早已预置 上海→上海市/武汉→湖北省武汉市）；
  `PolicyService.list_contest_regions` 返回 `distinct(DB) ∪ 常设赛区`。用户可预选，数据一旦入库
  即在工作台出现并推送；选了暂无数据时工作台为空（如实、不编造）。

## 接口与迁移

- **迁移 `f3a4b5c6d7e8`（现 head，新增 `source_crawl_states` 表）**——随 api 启动自动 upgrade。
- 新增 env `WEB_BASE_URL`（前端基地址，如 `http://118.196.142.222:8088`；留空不影响推送）。
- 无新增依赖。前端仅改 feed/sources 两页。

## 验证

- 前端 `tsc --noEmit` + `eslint`(改动文件) + `next build` 全绿。
- 后端离线 **376 passed, 7 skipped**（唯一 error 为既有需真库的 `test_get_status`，CI 一贯忽略）；
  新增：飞书倒计时/临期变色/按钮 3 项、抓取运行记录 0 条也刷新/运行优先 2 项 + 1 集成、
  常设赛区无数据仍可选 1 项。
- cnmaker 动态接口探查：homepage 200(22 条无上海/武汉)，action .xml GET/POST 均 302。

## 未完成 / 待办

1. **真机 ingest `cnmaker-contest` 验证**（延续 07-08 待办）：数据来源页赛事分区点抓取，入库后
   工作台地区卡片 + 档案参赛地区选项自动出现。属对外副作用（写共享库 + 推飞书）。
2. **配 `WEB_BASE_URL`**：想让飞书卡片出「打开工作台」按钮，在 dev `.env`/`.222` env 配前端地址。
3. **飞书交互卡片真机眼看**：确认 lark_md 链接与 header 配色渲染正常。
4. **部署 .222**：本轮 4 个 PR + 新迁移 `f3a4b5c6d7e8` 尚未上 .222（.222 仍停在 `15b4ac3`=#64~#69，
   连 #70/#72 都未部署）。测试上线阶段全量部署时须带上。
5. **聊天空白根治 PR**（`fix/mcp-init-hang`，见 07-08 handoff）仍未做；线上聊天已由用户手动配
   高德真 key 解决（治标）。

## 风险

- 飞书交互卡片渲染未真机验证（见待办 3）。
- 上海/武汉为"关注偏好"预选，短期大概率无数据、工作台空；能否真有赛事取决于创客中国官网是否
  把两地赛区上首页（不在我方控制）。
- 抓取仍对外副作用（写共享库 + 按关注地区推飞书），owner/admin 二次确认已提示。

## 下一步

1. 用户真机 ingest cnmaker + 眼看飞书卡片 + 配 WEB_BASE_URL。
2. 测试上线时部署 .222（带 4 PR + 迁移 `f3a4b5c6d7e8`）。
3. 有余力开 `fix/mcp-init-hang` 根治聊天空白 + alembic 日志。
