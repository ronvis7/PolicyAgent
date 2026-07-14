# 赛事双来源与独立赛事中心

更新时间：2026-07-14  
分支：`feat/contest-dual-sources`  
状态：实现与本地定向验证完成；尚未提交、部署或进行真机联调。

## 已完成

- 新增独立赛事中心 `/contests`：全部、官方来源、全网发现三个视图，并可按关键词、地区、来源筛选；工作台仍只保留企业画像与关注地区命中的推荐。
- 平台管理员可在赛事中心维护可信官方来源：创建、编辑、启停、连通性预检、手动抓取。首版仅接受 `cnmaker`、`wnd`、`gxt`、`cq` 四个已验证的门户模板。
- 企业 owner/admin 可维护本租户的全网赛事关键词订阅。每日任务依次执行：普通政策源、启用的官方赛事源、企业关键词发现；赛事仅在成为本租户新的 Feed 机会时推送。
- 全网发现复用 `BingSearchEngine`，但不使用聊天沙箱浏览器；搜索结果会抓取原文并校验赛事词、报名词、时效及重复链接，排除获奖、公示、名单、结果等页面。
- 公开赛事仍按 `source_url` 全局去重；新增 `contest_discovery_hits` 租户私有记录，同一公开原文可被多个企业分别命中/通知，但每个企业只通知一次，且不会泄露其订阅关键词。
- 赛事元数据写入 `policies.item_type`、`origin_type`、`source_name`；飞书卡片改为跳转 `/contests`。全网发现不再走原有“向所有租户扇出”的通知回调，而是仅通知命中的订阅企业。
- Alembic `a4b5c6d7e8f9`：回填现有赛事元数据、创建 `contest_sources`、`contest_subscriptions`、`contest_discovery_hits`，并播种既有五个官方赛事来源。

## 飞书赛事机会推送（2026-07-14 更新）

- 飞书不再推送新入库的全量赛事，也不再在每日重爬结束后发送全量/零条摘要。
- 只有当前租户新创建的赛事机会（`FeedItem.type=competition`）会推送；画像、关注地区、报名时效和已忽略状态以 Feed 重算结果为准。
- 无明确截止日期的赛事仅在发布时间 45 天内可进入 Feed，避免旧公告长期提醒。
- 飞书卡片“查看赛事机会”跳转 `/feed`；每条赛事附“**不再提醒此赛事**”，链接 `/feed?ignore={feed_item_id}`。登录后的页面调用既有 Feed 状态接口将该租户条目设为 `ignored`，后续重爬不会复推。
- 部署级 `FEISHU_WEBHOOK_URL` 不再参与赛事推送，因为它没有可用于判定赛事机会的租户画像。

## 接口

- `GET /api/contests`、`GET /api/contests/{id}`、`GET /api/contest-sources`
- 当前企业 owner/admin：`GET/POST/PATCH/DELETE /api/contest-subscriptions`
- 平台管理员：`POST/PATCH/DELETE /api/platform/contest-sources`、`POST /{id}/preflight`、`POST /{id}/ingest`

完整契约见 `.agents/API_CONTRACTS.md`，数据结构与隔离规则见 `.agents/DATA_MODEL.md`。

## 已验证

- 飞书优化定向验证：`test_feed_service.py` + `test_feishu_webhook.py` 共 **46 passed**。覆盖首次赛事机会推送、后续重爬不重复、未知截止旧赛事过滤、卡片忽略链接和按租户扇出。
- `npm.cmd exec tsc -- --noEmit` 已执行且未报错；`next build` 在本机 120 秒内仍停留于优化生产构建阶段而超时，未产生编译错误输出，明日需在测试环境复验完整 build。

- 后端：`16 passed`（新增赛事服务测试 + 既有入库服务测试）。覆盖订阅横向隔离、同一原文的公共去重、跨租户分别通知、同一租户不重复通知。
- 后端：`python -m compileall app alembic/versions` 通过。
- 前端：`npm.cmd exec tsc -- --noEmit`、`npm.cmd run build` 通过；`npm.cmd run lint` 无 error，保留项目既有 30 条 warning。
- `git diff --check` 通过。

正常全量 pytest 在当前机器被环境问题阻断：项目 `.venv` 的 Python launcher 指向缺失的 uv Python；改用可用解释器后，根 `conftest` 导入 MCP 时缺少 `pywintypes`。定向服务测试以 `--confcutdir` 运行，未受影响。

## 明天真机验收

1. 在测试环境执行 Alembic upgrade，确认五个官方来源已播种、既有赛事已回填 `competition/official`，并检查 `contest_discovery_hits` 唯一约束。
2. 用平台管理员登录 `/contests`：预检一个兼容模板来源，手动抓取后确认赛事中心可见、来源标签正确；再停用来源并确认定时任务不会抓取它。
3. 用租户 A、B 创建相同关键词：同一原文只出现一条公开赛事；A、B 各收到一次自己的通知；A 再次运行不重复通知；两租户互相不能读取或修改订阅。
4. 用广告、获奖公示、已结束赛事和无效链接验证不会入赛事中心或发送通知。
5. 确认未命中画像的赛事仍可在 `/contests` 检索，而工作台只出现命中画像和关注地区的推荐；飞书按钮跳到 `/contests`。

## 风险与后续

- Bing HTML 结果结构、访问频率和服务条款可能变化；已通过 `SearchEngine` 接口隔离，后续可替换合规搜索 API。
- 目前赛事中心的官方来源卡片显示来源配置；旧“数据来源”页仍使用静态注册表的健康度视图。若要在旧页同步展示管理员动态来源，可作为后续独立改动。
- 真机抓取、飞书 webhook、定时调度与迁移尚未在真实 PostgreSQL 环境验证，完成上述验收后再部署。
