# 赛事机会重启 + 飞书新赛事即推 + 参赛关注地区（比赛机会类型落地）

Issue：—
分支：PR **#64 已合并 main**；PR **#65**（`feat/feishu-contest-push`）、PR **#66**（`feat/contest-regions`）已开待合并
负责人：—
更新时间：2026-07-06

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

## 未完成 / 下一步

1. **合并 #65、#66**（等 CI；两者改动无重叠，顺序随意。⚠️ 教训：#64 合并删分支时 #65 曾被
   GitHub 连带关闭，已恢复 base=main——**叠 PR 先改 base 再删分支**）
2. **飞书机器人配置**：建群→添加"自定义机器人"→开签名校验→URL/secret 进服务器 `.env`→重建栈→
   手动抓 wnd-contest 联调（群里应收「🏆 新赛事机会」卡片）
3. **PR3 重庆爬虫**：kjj/jjxxw 已探活，待逆向列表接口（参考 shyp/gxt 先例）；落地后"重庆市"
   选项自动出现在参赛地区多选
4. 真机走查：抓赛事源→Feed 赛事分栏→选关注地区→重新匹配只剩所选地区→飞书收卡片
5. 候选增强：档案选沪/渝后可考虑为 shyp 加赛事子源（需确认其 CMS 搜索接口支持关键词）；
   推送的 env 级地区过滤（见风险 3）

## 风险

1. **"大赛"关键词有噪音**：获奖公示/新闻报道也命中（真机冒烟已见）。先上线观察，
   噪音大再收紧（如标题同时含"举办/申报/征集"或排除"获奖/公布"）
2. gxt dataproxy 跨页返回重复条目（分页窗口重叠），靠 source_url upsert 去重，条数统计以库内为准
3. **飞书推送不按关注地区过滤**：webhook 是部署级、关注地区是租户级，对不上；当前来源本就按需接入、
   噪音有限。要过滤加 env 级地区白名单即可（#66 PR 描述已注明）
4. 赛事只在匹配 top_k 内与政策同池竞争排名，档案关键词与比赛通知重合弱时可能不进 Feed；
   如赛事覆盖率不足，后续可给 competition 单独保底名额
