# 政策申报截止日期跟踪 + 主动提醒（主线⑤ v1）+ 项目申报通知爬虫源

更新时间：2026-06-17
分支/PR：`feat/policy-apply-deadline`（待开 PR）。

## 背景

报告生成流水线价值存疑（资质申报实际在官网平台填报，报告只是信息重排）。改做更契合「主动情报」
定位、与官网申报互补的能力：**「XX 政策申报还有 N 天截止」** 的临期提醒。申报截止日期源站不给
结构化字段、只埋在正文自然语言里，故用 **LLM 抽取 + "待核对"纪律**（抽不到标未识别、绝不编造、
抽到的带原文窗口+免责提示，沿用资质 A1/A2 风险纪律）。

## 实现

- **`Policy` 加三字段**：`apply_deadline` / `apply_window_text` / `deadline_status`(extracted/rolling/unknown)。
- **`deadline_extractor.py`（新）**：纯函数(prompt 构造 + 结果解析) + LLM 封装。found 为假/日期非法/
  JSON 损坏/调用异常**一律回退 unknown**；正文超长取首尾两段控 token。
- **②入库编排**：`PolicyIngestService` 注入平台默认 LLM(系统级、无租户)，逐篇 best-effort 抽取；
  平台无 key 时吞掉传 None，**绝不阻断入库**(同向量双写纪律)。
- **提醒机制(复用 Feed，零提醒表)**：截止快照(`apply_deadline`/`deadline_status`)落 `policy_matches`，
  新增 `GET /feed/expiring?within_days=14`(仅 extracted 且未 ignored，按截止升序)；`days_left` 读取侧派生。
- **前端**：Feed 列表临期徽章(≤3天红/≤14天琥珀/已过期删除线/常年受理)；政策详情弹窗截止区块 +
  原文窗口 + "系统自动抽取、可能有偏差、以原文与官方平台为准"免责提示。
- **迁移 `a8b9c0d1e2f3`（现 head）**：policies + policy_matches 加列，纯新增 + `apply_deadline` 索引。

## 关键转折：换数据源（真机走查发现）

**第一次走查**：对原「政策文件」栏目(`wnd`)实抽 40 篇 → **0 extracted**、0 误报 0 漏报。根因不是
代码，而是**该栏目结构上不带申报截止日期**——装的是政策文件/行动方案/管理条例/解读图解。申报截止
日期住在**项目申报通知**里(各部门"请于 X 月 X 日前申报")。

**修复**：扩 wnd 爬虫支持**按标题关键词全站检索**(逆向确认 `/info_open/search` 的 `title` 字段才真正
过滤标题；`keyword`/`searchWord` 不过滤)，新增来源 `wnd-apply`(`title_keyword='申报'`)。`WndPolicyCrawler`
加 `title_keyword`/`source` 参数：有关键词走 title 检索(无 channelIds)，否则走政策文件 channelIds。

**第二次走查**(连 .222，2026-06-17)：`ingest('wnd-apply', max_pages=3)` 抓 60 篇 →
**extracted 23 / unknown 37 / rolling 0**。抽取真实且处理了难点：窗口"11月11日—11月17日"取末(11-17)、
"延长至11月7日"取延长后、"截止7月18日"(省略年份)按"2025年度"推出 2025、多档"A/D类截止8月31日"取最终。
37 unknown 为纯附件 PDF(正文空)/结果公示(无未来截止)——正确降级。`FeedItemResponse.days_left`
对未来/过期/未知分别 5 / -2 / None 序列化正确。全量 **169 passed**(1 error 为既有需真库 test_get_status)。

## 后续 / 注意

- **`wnd-apply` 数据已保留在 .222**(60 篇真实申报通知 + 向量入公开库，同 ② 保留真实数据惯例)；
  也顺带增强了 Agent/RAG 对"怎么申报"的作答素材。
- 当前样本截止多为过去日期(门户里是历史申报通知)，`/feed/expiring` 现多为空；待**当前批次申报通知发布**
  (如 2026 年度专项资金开始申报)后自动有未来截止可提醒。需定期重爬 `wnd-apply` 保鲜。
- **附件型申报指南抓不到正文**(div#Zoom 空、内容在 PDF 附件)→ 落 unknown。要覆盖需下载解析附件(未做)。
- 多区域同理：每个门户的申报通知需各自确认检索/栏目可逆向(①b/②教训)。
- 前端 Feed「重新匹配」/抓取后会把截止快照带进各租户 Feed；UI 功能性回归由项目组自测。
