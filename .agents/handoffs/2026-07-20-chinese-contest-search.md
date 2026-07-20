# 中文赛事全网搜索优化

日期：2026-07-20
分支：`fix/chinese-contest-search`
状态：代码、离线定向验证和本地真实百度 Key 冒烟完成；未提交、未部署 `.222`。

## 完成内容

1. 新增 `BaiduSearchEngine`，调用百度千帆 v2 `POST /v2/ai_search/web_search`，返回值适配既有
   `SearchEngine` / `SearchResults` 领域接口；支持 `top_k` 1~50 和周/月/年时效映射。
2. 新增 `FallbackSearchEngine`。赛事搜索配置为 `auto`/`baidu` 且存在百度 Key 时走百度；接口失败或
   空结果按配置回落 Bing。缺 Key 不阻断 API 启动，会明确告警并回落。
3. 新增环境变量：
   - `CONTEST_SEARCH_PROVIDER=auto|baidu|bing`
   - `BAIDU_SEARCH_API_KEY`
   - `CONTEST_SEARCH_TOP_K`（默认 20）
   - `CONTEST_SEARCH_FALLBACK_ENABLED`（默认 true）
4. 赛事发现查询从 Bing 布尔表达式改为搜索提供方无关的短中文查询；检索窗口由最近 30 天扩大到最近
   1 年，后续仍由报名意图、赛事意图和既有入库/Feed 截止规则过滤。
5. 候选最多处理前 30 条，5 并发抓正文；删除脚本、导航、页眉页脚、侧栏并优先提取 article/main/
   常见正文容器，避免相关推荐中的“公示/结果”误杀报名通知。
6. 新增确定性评分：企业关键词相关性 + 赛事意图 + 报名意图 + 截止提示；“获奖/公示/名单/结果”只在
   标题出现时一票否决，正文提及往届结果不再误杀。
7. 每日批处理中，规范化后相同的租户关键词共享一次搜索与网页抓取；公开赛事仍按 URL 全局去重，
   `contest_discovery_hits` 仍按租户分别记录和通知。

## 验证

- `pytest` 搜索适配 + 赛事服务 + 政策入库：**27 passed**。
- `python -m compileall -q app core alembic/versions`：通过。
- PR #83 首轮后端 CI 暴露 8 项存量测试失效：7 个 Feed “当前赛事”夹具固定为 `2026-06-01`，到
  当前日期已超过 45 天有效期；另 1 个入库摘要期望缺少既有 `item_type` 字段。经用户同意一并维护测试：
  当前赛事改用 `date.today()`，摘要补齐字段断言，未改生产逻辑。
- CI 等价完整后端套件：**400 passed / 7 skipped**。
- `git diff --check`：通过。

### 真实百度搜索冒烟（只读，不入库、不通知）

- 用户提供的 Key 仅写入 gitignored 根 `.env`，`git check-ignore -v .env` 已确认命中忽略规则；未把 Key
  写入源码、Git diff 或共享记忆。
- 直接调用百度 v2：`success=True`，返回 10 条中文赛事，标题/摘要/URL 字段适配正常；未再出现 Bing 的
  汉语词典释义噪声。结果覆盖赛事启动通知、高校竞赛、微信公众号和媒体转载。
- 完整 `_discover_candidates("人工智能")` 只读链路：searched=10、valid=9，正文抓取与评分可用。
- 其中 1 条“决赛即将启幕”属于赛事新闻而非开放报名；随后把“决赛/复赛/入围/晋级/颁奖/闭幕/回顾”
  加入标题级排除，并补确定性回归测试。

## 部署与真机验收

部署 `.222` 前在服务器 `.env` 写入（不要提交真实 Key）：

```dotenv
CONTEST_SEARCH_PROVIDER=auto
BAIDU_SEARCH_API_KEY=<百度千帆 API Key>
CONTEST_SEARCH_TOP_K=20
CONTEST_SEARCH_FALLBACK_ENABLED=true
```

重建 `policy-api` 后检查启动日志不再出现“BAIDU_SEARCH_API_KEY 未配置，回落 Bing”。用 owner/admin 建立
“人工智能”等测试订阅并手动运行，确认：

1. run 的 `searched_count` 大于 0，候选不再出现词典释义；
2. 报名通知进入赛事中心，获奖名单/结果公示不进入；
3. 同一关键词再次运行不重复建立租户命中；
4. 第二租户同关键词仍获得自己的私有命中；
5. 暂时填错 Key 时能回落 Bing，运行不会因搜索提供方异常而崩溃。

## 变更边界与风险

- 零数据库迁移、零公开 HTTP API 变化、零新增 Python 依赖。
- 本地已验证真实 Key、响应字段和一次完整候选链路；尚未验证 `.222` 容器网络、定时任务限流、真实入库
  与租户飞书通知，因此部署后仍需完成上述真机验收。
- Bing 仅作可用性兜底，其中文质量问题仍然存在；若百度真实 A/B 仍不理想，下一步可在同一接口下接入
  智谱 `search_pro_sogou`，不需要改赛事服务。
