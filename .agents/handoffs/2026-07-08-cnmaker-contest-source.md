# 创客中国官网全国赛事源 + 参赛地区选项数据驱动（赛区拓展）

Issue：—
分支：`feat/cnmaker-contest-crawler`（PR #72，**已合并 main** `257ee62`，CI 三绿）
负责人：—
更新时间：2026-07-08

## 目标

赛区拓展（用户点名新增武汉、上海；江苏/重庆已有）。经甄别，改走全国赛事平台一次覆盖多地，
交付创客中国官网赛事源 + 把「参赛关注地区」选项改为数据驱动。顺带修复本地聊天空白 bug。

## 已完成

### A. 赛区甄别（决定不逐个逆向地方门户）

- **武汉/上海政府门户没有稳定、当季的赛事栏目**：武汉科技局(`kjj.wuhan.gov.cn`)/经信局
  (`jxj.wuhan.gov.cn`)是 TRS WCM（技术上可抓，经信局列表标题嵌日期需取 `.art_list_ttl`），
  但通知栏目全是认定/公示/申报/绩效，无可报名大赛；上海科委(`stcsm.sh.gov.cn`)是 TRS 系但
  列表聚合页 + hash URL + JS 翻页，需新爬虫。创业大赛通知分散在**微信公众号 / 大赛独立官网
  (startup-sh.cn / cnmaker.org.cn) / 各区零散转发**，且 2026 这批报名多已截止（会被保鲜挡）。
- **创客中国官网 `cnmaker.org.cn` 现可访问**（交接文档 07-06 记的"连不上、放弃"已变），首页
  静态渲染当季主推赛事，一个源覆盖全国各省市赛区 + 全国性行业赛 → **投入产出远高于逐个逆向**。
- 用户拍板：接 cnmaker 静态全国源（首页当季赛事，稳、低成本）。**局限**：首页主推当前
  不含武汉/上海（在 5 层封装的 SiteBuilder 动态接口 `getcompetitionlieb.xml` 后、覆盖存疑），
  若它们后续上首页会自动出现。

### B. CnmakerContestCrawler（新爬虫，PR #72）

- 抓官网首页 `a.game_boll`（`label.tips` 状态 / `h3` 标题 / `p>span` 分类+年月 /
  `ds/detail/{hash}.html` 详情链接）+ 详情正文 `div.competition-intronr`。
- **分类→标准 region 映射**（纯函数 `map_region`）：地级市挂靠省（深圳→广东省深圳市）、直辖市/
  自治区规范化、行业赛（生物医药/低空经济等）归 `全国`。已预置武汉→湖北省武汉市、上海→上海市。
- 按 `source_url` 去重（首页多 tab 重复渲染）、排除「已结束」、复用赛事保鲜过滤 `list_filter`。
- 真机实抓 **12 条**（深圳/云南/新疆/辽宁/安徽赛区 + 7 个全国行业赛），地区映射/正文/保鲜均正确。

### C. 参赛关注地区选项数据驱动（解决"一源多地区"）

- 根本矛盾：cnmaker 一个来源产出多地区赛事，而旧前端选项从**单值** `source.region` 去重取，
  且填"全国"又匹配不了具体省市（`contest_region_matches` 前缀匹配对"全国"无效）。
- 改为数据驱动：仓储 `distinct_contest_regions(sources)`（DB + 内存 fake）→
  `PolicyService.list_contest_regions()`（取赛事来源已入库政策的 region 去重）→
  新增 `GET /policies/contest-regions`（**注册在 `/{policy_id}` 之前**）→ 前端
  `ContestRegionPicker` 改调该端点。
- 效果：cnmaker 入库后深圳/云南/北京等选项**自动出现**，与 Feed 过滤同用 `policy.region`
  自洽，只显示真有赛事的地区；对已有江苏/重庆赛事**向后兼容**（甚至更准，不显示 0 条的源地区）。

### D. 聊天空白 bug（本地已修）

- 用用户申请的高德真 key 替换 `api/config.yaml` 的占位 amap 条目、`enabled` 改 true。
- 真机验证：容器内复跑原 120s 悬挂的 MCP 初始化，现 **1.4s 完成、36 工具**（高德 15 + jina 21）。
- **注意**：`config.yaml` 是 gitignored 运行时文件，**不在 PR 内**；.222 线上仍是占位 key、
  聊天照样悬挂，须登服务器改同一行。见 handoff `2026-07-08-chat-blank-mcp-hang-and-contest-regions`。

## 接口与迁移

- **零迁移、零新增依赖**。新增只读端点 `GET /policies/contest-regions`（返回 `List[str]`）。
- `POLICY_RECRAWL_SOURCES` 默认值追加 `cnmaker-contest`（随 04:00 定时重抓）。

## 验证

- 全量离线 **371 passed**（唯一 error 为既有需真库的 `test_get_status`，CI 一贯忽略）。
- 前端 **tsc + eslint 全绿**。CI 三 job（backend/frontend/integration）全 pass。
- 真机：爬虫实抓 12 条；新端点经 nginx `/api/policies/contest-regions` 返回 401（路由/顺序正确）。

## 未完成

1. **真机 ingest 未做**（用户明天测）：会**写共享库 + 按参赛地区触发飞书推送**（既有"新赛事即推"），
   属对外副作用，留用户在前端点「抓取」选 `cnmaker-contest`，或等次日 04:00 定时重抓触发。
   入库后前端「参赛关注地区」会自动多出深圳/云南等选项。
2. **.222 线上聊天 bug 未修**：服务器 config.yaml 仍占位 key，须手动改（换 key + enabled:true）重启。
3. **聊天 bug 根治 PR 未做**：enabled 过滤 + 连接超时 + best-effort + alembic 日志修复
   （见 chat-blank handoff「未完成 2/3」）。config.yaml 配真 key 只治标，MCP 服务再抖动仍会全站空白。
4. **前端 UI 待改**（用户提）：①「参赛关注地区」chips 拥挤；②公开政策/赛事时间筛选默认取到 24/25 年
   （今年 26 年 7 月），需校正默认时间窗。均属后续单独一轮。
5. **武汉/上海直接覆盖**：cnmaker 首页当前无；如需必接其 5 层动态接口（脆弱）或上浏览器渲染，暂缓。

## 风险

- cnmaker 首页静态只主推十几个当季赛事，量随官网运营变化；完整全国列表在动态接口后未接。
- 真机 ingest 的飞书推送按租户 `contest_regions` 过滤扇出，配了 webhook 的组织会收到卡片。

## 下一步

1. 用户真机 ingest `cnmaker-contest` 验证入库 + 前端地区选项/Feed 赛事分栏。
2. .222 config.yaml 改高德 key 恢复线上聊天；随后开 `fix/mcp-init-hang` 根治 + 日志修复。
