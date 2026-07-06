# 赛事机会重启 + 飞书新赛事即推 + 参赛关注地区（比赛机会类型落地）

Issue：—
分支：PR **#64/#65/#66/#67 全部已合并 main**（#67=`feat/feishu-tenant-webhook`，webhook 前端配置）
负责人：—
更新时间：2026-07-07（三更：#67 评审修复后合并；**代码侧本轮全部收口，剩部署+真机联调**，见下"明日操作清单"）

## 目标

老板转向：**轻量化收集适合初创公司的创业类比赛 + 飞书群主动推送**，并支持多地区关注
（如同时关注重庆/无锡/上海）。比赛机会类型 2026-06-15 因"公众号难爬"暂缓，本轮按新路线重启：
**政府门户关键词子源绕开公众号**——创客中国/i创杯/创新创业大赛的赛区通知本来就发省市门户，
而门户我们已有成熟爬虫框架。

## 已完成

### PR #64（已合并 main）：赛事子源 + Feed type=competition
- registry 加 `wnd-contest`/`gxt-contest`（`title_keyword="大赛"`，复用 wnd-apply 全站检索
  / gxt 列表过滤两种既有模式）+ `CrawlerSource.item_type` 分类 + `competition_source_keys()`；
  入库编排/端点/数据来源页零改动自动出现
- `FeedItem.from_policy_match` 支持 `item_type`；`FeedService` 按 `policy.source ∈ competition_sources`
  打 `type=competition`（④ 预留列启用，**零迁移**）；`with_snapshot_from` 把 type 纳入快照(来源重分类自愈)
- `POLICY_RECRAWL_SOURCES` 默认追加两子源；⑤截止抽取自动覆盖**报名截止**
- 前端工作台加「赛事机会」分栏 + 紫罗兰徽章/彩条；赛事复用政策详情弹窗与截止徽章
- **顺手修真 bug**：gxt 爬虫关键词过滤后空页误判"到底"提前停止翻页（低频词"大赛"几乎每页滤空，
  gxt-contest 恒抓 0 条）。修为按原始记录判底、过滤后置；详情仍只抓命中条目

### PR #65（待合并）：飞书群机器人新赛事即推
- `PolicyIngestService` 入库前按 source_url 批量比对存量识别**首次入库**（summary 加 `new`，
  同批跨页重复去重）+ 可选 `on_new_policies(source, new_policies)` 回调（best-effort，异常不阻断入库）
- `infrastructure/external/notify/feishu_webhook.py`：`feishu_sign`（官方 HMAC-SHA256+base64）/
  `build_contest_message`（post 富文本：标题原文链接+地区/发布/报名截止；单条上限 10 防刷屏）纯函数 +
  `FeishuWebhookNotifier.send`（httpx，transport 可注入离线测试）+ `make_contest_push_hook`
  （**仅赛事来源触发**，普通政策入库不打扰群）
- env `FEISHU_WEBHOOK_URL`/`FEISHU_WEBHOOK_SECRET`（留空=不推送零行为变化，无硬编码）

### PR #66（待合并）：参赛关注地区多选
- `EnterpriseProfile.contest_regions`（attributes JSONB，**零迁移**，老数据缺键=不限）
- 纯函数 `contest_region_matches`：层级前缀**双向**命中（选省含辖内区县赛事；选区县含省级赛事）；
  未选=不限；赛事无地区且已选=不命中
- `FeedService` 物化时按关注地区过滤 competition 条目；政策/资质不受影响
- `/policies/sources` 增量透出 `item_type`；前端档案页「参赛关注地区」徽章多选
  （选项动态取自赛事来源地区——**新地区爬虫接入后选项自动出现，前后端零改动**）

### 甄别与真机冒烟
- **全国赛事平台放弃**：创客中国(cnmaker.miit.gov.cn)/中国创新创业大赛官网(cxcyds.com)连不上
- **重庆已探活可逆向**：kjj.cq.gov.cn(科技局)/jjxxw.cq.gov.cn(经信委)/cq.gov.cn 均 200（PR3 素材）
- 真机冒烟：wnd-contest 1 页 20 条（含「飞凤杯」创新创业大赛，正文 2026 字；部分老条目源站已下架 404 容错正常）；
  gxt-contest 修复翻页后 8 页 10 条（创客中国省赛/i创杯/信息消费大赛，正文全非空，通知多在第 5 页后）

## 接口与迁移

**零迁移、零新增依赖、全程无硬编码机密。** 增量接口：`/policies/sources` 加 `item_type`、
档案 GET/PUT 加 `contest_regions`（均向后兼容）。新 env：`FEISHU_WEBHOOK_URL`/`FEISHU_WEBHOOK_SECRET`。
`POLICY_RECRAWL_SOURCES` 默认值追加 `wnd-contest,gxt-contest`。

## 验证

- #64：全量离线 300 passed，CI 三项全绿后合并；#65：316 passed（其分支）；#66：310 passed（其分支）+
  前端 tsc/eslint/build 全绿。各 PR 均带 TDD 新增单测（合计 ~24）
- 真机冒烟见上；**服务器 .222 未部署本轮改动**（合并后按需 `up -d --build`）

## 明日操作清单（2026-07-08 起手，代码零改动，纯操作）

1. **部署 .222**：服务器上 `docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build`
   （本轮 #64~#67 均未上服务器；迁移 `e2f3a4b5c6d7` 随 api 启动自动 upgrade，确认 api/ui healthy）
2. **飞书联调（走设置页，不动 .env）**：建飞书群 → 群设置添加「自定义机器人」（建议开"签名校验"）→
   复制 webhook 地址/密钥 → 登录 owner/admin 账号 → 设置弹窗「飞书推送」页签贴入并保存 →
   点「发送测试消息」，群里收到 ✅ 即通
3. **赛事动线真机走查**：数据来源页手动抓 `wnd-contest`（如有新增，群里应收「🏆 新赛事机会」卡片）→
   工作台 Feed「赛事机会」分栏出现 → 企业档案选「参赛关注地区」→ 重新匹配后赛事只剩所选地区
4. 完事后如继续开发：**PR3 重庆爬虫**（kjj.cq.gov.cn / jjxxw.cq.gov.cn 已探活 200，逆向列表接口
   参考 shyp/gxt 先例；落地后"重庆市"自动出现在参赛地区选项与推送过滤）

## 未完成 / 下一步

1. ~~合并 #65、#66~~ **已合并**（#65 恢复后分支无 CI run，空提交补跑三绿后合入）
2. ~~飞书配置改前端~~ **已合并**（PR **#67**，按用户决定"前端配 webhook、不走 env"）：
   - 租户级存储 `tenant_settings.feishu_config`(JSONB 可空列，迁移 `e2f3a4b5c6d7` **现 head**)；
     设置弹窗新增「飞书推送」页签(owner/admin)：URL/secret 表单+脱敏回显+**发送测试消息**+停用
   - 新赛事入库按租户**扇出**推送，并按各租户档案 `contest_regions` 过滤——**顺带解决风险 3**；
     env `FEISHU_WEBHOOK_URL` 保留为部署级全量兜底(两级组合)
   - 已过 8 角度代码评审并修复：ORM 三 JSONB 列加 `none_as_null=True`(显式 None 落 SQL NULL，
     否则 `IS NOT NULL` 过滤匹配所有行，配真库集成测试回归)；换 webhook 地址时**不沿用旧 secret**
     (防换群后签名错静默失败)；URL 白名单只认 `https://open.feishu.cn/`/`open.larksuite.com`(防 SSRF)；
     已配置后 URL 留空=保留(支持只轮换 secret)；扇出并发 gather
   - **联调步骤(合并部署后)**：建群→添加"自定义机器人"(可开签名校验)→设置页「飞书推送」贴入→
     发送测试消息→手动抓 wnd-contest 验证群收「🏆 新赛事机会」卡片。**不再需要动服务器 .env**
3. **PR3 重庆爬虫**：kjj/jjxxw 已探活，待逆向列表接口（参考 shyp/gxt 先例）；落地后"重庆市"
   选项自动出现在参赛地区多选
4. 真机走查：抓赛事源→Feed 赛事分栏→选关注地区→重新匹配只剩所选地区→飞书收卡片
5. 候选增强：档案选沪/渝后可考虑为 shyp 加赛事子源（需确认其 CMS 搜索接口支持关键词）。
   评审遗留小项(未修，规模小可后补)：扇出内企业档案逐租户查询(N+1，租户少可忽略)、
   `make_contest_push_hook` 与租户扇出可共享 `_push` 小助手、停用推送无二次确认(与 MCP/A2A 删除一致)

## 风险

1. **"大赛"关键词有噪音**：获奖公示/新闻报道也命中（真机冒烟已见）。先上线观察，
   噪音大再收紧（如标题同时含"举办/申报/征集"或排除"获奖/公布"）
2. gxt dataproxy 跨页返回重复条目（分页窗口重叠），靠 source_url upsert 去重，条数统计以库内为准
3. **飞书推送不按关注地区过滤**：webhook 是部署级、关注地区是租户级，对不上；当前来源本就按需接入、
   噪音有限。要过滤加 env 级地区白名单即可（#66 PR 描述已注明）
4. 赛事只在匹配 top_k 内与政策同池竞争排名，档案关键词与比赛通知重合弱时可能不进 Feed；
   如赛事覆盖率不足，后续可给 competition 单独保底名额
