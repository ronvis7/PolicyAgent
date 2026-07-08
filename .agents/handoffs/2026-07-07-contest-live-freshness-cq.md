# 赛事动线联调 + 入库去重修复 + 赛事三层保鲜 + 重庆爬虫（PR #68/#69）

Issue：—
分支：**PR #68 `feat/contest-freshness-filter`（待合并）→ PR #69 `feat/cq-contest-crawler`（stacked 于 #68，待合并）**
负责人：—
更新时间：2026-07-07（续 `2026-07-06-contest-opportunities-feishu`，其"明日操作清单"第 2/3 步已完成、第 1 步部署 .222 仍未做）

## 背景与关键发现

用户真机联调：飞书 webhook 测试消息**已通**（设置页动线 OK）；但档案选"江苏省"后工作台**零比赛**。
排查结论（重要，避免再误判）：

1. **不是匹配/过滤 bug**：`contest_region_matches` 层级前缀双向匹配正确；根因是**共享库(policy-postgres@.222)从未抓过赛事源**——数据来源页手动抓取这步(前交接清单第 3 步)一直没做。
2. **服务器 .222 仍是两周前的旧代码**（容器 Up 2 weeks，#64~#67 均未部署）；用户能用上设置页是因为**本地 dev 栈(新代码)连共享库**在跑，迁移 `e2f3a4b5c6d7` 也是它自动升的。公网 8088 演示前必须先部署。

## 已完成

### 真机抓取 + 修真 bug（入库同批去重，随 #68 合入）
- `wnd-contest` 首抓 11 条成功；`gxt-contest` 首抓**整批回滚**——gxt dataproxy 分页窗口重叠跨页返回重复条目，
  `PolicyIngestService` 只在**推送侧**(_detect_new)做了同批去重，落库循环没有：同事务内第二条重复 url 的
  SELECT 看不见未提交的第一条，双双 INSERT 撞 `uq_policies_source_url` → 整批回滚(交接风险 2 的
  "靠 upsert 去重"未覆盖同批内重复；冒烟没炸只是当时恰无跨页重复)。
- **修复**：`ingest` 抓取后 `_dedupe_by_source_url` 整批去重再进后续所有环节；原有去重测试加严到断言
  `crawled/upserted`(假 UoW dict 存储曾把 upsert 侧问题盖住)。修复后 gxt-contest 原始 15 条去重 6 条入库成功。

### PR #68：赛事三层保鲜（用户诉求"过期比赛不抓不推，推送要对口+实时"）
仅赛事子源生效，政策来源零行为变化：
- **列表级**(新增 `crawler/list_filter.py` 纯函数)：发布超 `CONTEST_MAX_AGE_DAYS`(默认 180 天，env 可调，
  0/负值=不限)或标题含 `获奖/公示/公布/名单/结果`(registry `_CONTEST_EXCLUDE_WORDS`)的条目在**详情抓取前**
  跳过，省详情 HTTP/LLM 截止抽取/向量化三笔开销；列表按日期倒序，整页过旧提前停止翻页(缺日期条目保守保留)。
- **入库级**：赛事来源抽出申报截止且已过期 → 不入库不向量化不推送(`skip_expired_sources=
  competition_source_keys()` 接线，summary 新增 `skipped_expired`)；抽不出截止(unknown)保留不误杀。
- **Feed 级**：截止已过的赛事不再物化，存量比赛过期后自然从工作台消失；政策/资质不受影响。

### 存量清理（用户确认后执行，共享库）
- 按新规则筛查：**库内 17 条赛事全部命中**(2013~2025 喜报/获奖公示/已结束比赛，含 Feed 里的 2025 飞凤杯)。
- 已删：17 policies + 27 document_chunks + 17 knowledge_files + 2 policy_matches(competition)，验证归零。
- **重要事实：两江苏源当前无在报名期比赛**(wnd 门户 13 个月、gxt 门户 2 年半没发新"大赛"通知)，
  赛事分栏空 = 正常态，非 bug。新比赛靠每天 04:00 定时重抓自动入库+推送。

### PR #69：重庆赛事爬虫（PR3，stacked 于 #68）
- **逆向(2026-07-07)**：kjj.cq.gov.cn(科技局)与 jjxxw.cq.gov.cn(经信委)同属 **TRS WCM 静态站**——
  静态分页 `index_{n}.html`(总页数在页内 `createPage(N,...)`)、详情链接 `tYYYYMMDD_{id}.html` 路径自带日期、
  正文 `div.trs_editor_view`(kjj 外层 `.zwxl-article`)。条目模板两套(kjj=li 内 a[title]+兄弟 span /
  jjxxw=a 内嵌 p+span)，一套解析兼容。
- 新增 `CqPolicyCrawler`(base_url/column_path 参数化，同类可注册更多市级委办局栏目)；registry 登记
  `cqkjj-contest`(通知公告栏 /zwxx_176/tzgg/)、`cqjjw-contest`(公示公告栏 /zwgk_213/gsgg/，创客中国
  重庆赛区阵地)，region=重庆市、competition、接 #68 保鲜；`POLICY_RECRAWL_SOURCES` 默认追加。
  入库编排/端点/前端零改动，「参赛关注地区」选项自动出现"重庆市"。
- **真机(已入共享库)**：`cqkjj-contest` 5 条**全部在报名期**——第二届"渝创星火"科技成果转化大赛
  (正文 3680 字)、第十五届中国创新创业大赛重庆赛区暨第十二届"高新杯"众创大赛(+两条**报名延期至
  7 月 17 日**的通知)、评审专家征集；历史喜报/获奖公示被保鲜过滤全部拦掉。`cqjjw-contest` 0 条符合预期
  (公示类被排除词拦截)。

## 接口与迁移

零迁移(head 仍 `e2f3a4b5c6d7`)、零新增依赖。新 env：`CONTEST_MAX_AGE_DAYS`(默认 180)。
`POLICY_RECRAWL_SOURCES` 默认值追加 `cqkjj-contest,cqjjw-contest`。ingest summary 新增
`skipped_expired` 键(向后兼容)。

## 验证

- #68：全量离线 351 passed(新增 ~12 例)；#69：362 passed(新增 11 例)。均已 push 待 CI。
- 真机：两江苏源+重庆两源抓取入库全流程通；本地 dev 栈已重建至 #69 代码(连共享库)。

## 明日操作清单（2026-07-08）

1. **合并 PR**：#68 CI 三绿合并 → #69 自动 retarget main → CI 三绿合并。
2. **部署 .222**：`docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build`
   （把 #64~#69 一次带上；无新迁移，api 起来即好，确认 api/ui healthy）。
3. **档案勾"重庆市"**：企业档案 →「参赛关注地区」→ 勾新出现的"重庆市" → 重新匹配 →
   工作台「赛事机会」应出现 5 条重庆比赛。**注意：这 5 条不会补发飞书卡片**——入库扇出发生在
   抓取时刻，当时用户只选了江苏省被地区过滤掉了；已入库条目不再是"新增"。验证飞书用
   「发送测试消息」，或等下次定时重抓有真新增时收卡片，**别把"没收到推送"误判为 bug**。
4. **平台 LLM key 充值**（API 402 Insufficient Balance）→ 数据来源页重抓 `cqkjj-contest` 补
   截止抽取(5 条现全 unknown，Feed 无截止徽章；"高新杯"已延期至 7/17 较急)。

## 风险 / 注意

1. **平台 LLM key 余额不足(402)**：⑤截止抽取全回退 unknown(设计内 best-effort)，入库/推送不受影响；
   充值前所有新入库条目都没有截止徽章，入库级"过期跳过"也不会生效(抽不出截止=不判定)。
2. 重庆 5 条已入库未推送(见上清单第 3 条)，勾选地区后只进 Feed 不补推。
3. `cqjjw-contest`(经信委公示公告栏)大赛通知频率低且公示类居多，0 条为常态；创客中国重庆赛区
   开赛季自动进来。如需更高覆盖可再逆向经信委"中小企业处"子栏目。
4. 时效窗口 180 天是"宁多勿漏"起步值；若嫌旧(如去年省赛通知)可 env 收紧到 90。
5. #67 评审遗留小项照旧未修(扇出 N+1/共享 _push 助手/停用无二次确认，规模小可后补)。
