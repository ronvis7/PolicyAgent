# 每日赛事摘要「不再提醒此赛事」按钮 + 全网发现排查

日期：2026-07-19

## 已完成

### 1. 每日摘要逐条忽略按钮

**问题**：飞书每日赛事摘要（10:00 定时）没有逐条「不再提醒此赛事」按钮，只有即时推送有。

**修改**：
- `feishu_webhook.py` — `build_contest_daily_summary_message` 新增 `feed_item_ids` 参数，每条赛事展示忽略按钮
- `feishu_webhook.py` — `make_tenant_contest_daily_summary_hook` 的 `push_one` 查询租户 Feed 条目构建 policy_id→feed_item_id 映射
- 为尚未进入 Feed 的赛事自动创建 FeedItem（如被时效过滤掉的历史赛事），确保所有展示条目都有按钮
- 已忽略的赛事自动从摘要中排除

### 2. 免登录签名链接

**问题**：飞书卡片按钮跳转网页需要登录，用户体验差。

**方案**：HMAC 签名链接，无需登录态即可标记忽略。

**修改**：
- `feishu_webhook.py` — 新增 `_feed_ignore_signed_url()` 函数，用 JWT 密钥 HMAC-SHA256 签名(有效期 30 天)
- `feed_routes.py` — 新增 `GET /api/feed/ignore-direct` 端点，验证签名后直接标记忽略，返回精简 HTML 页面
- 三个 hook 工厂函数透传 `signing_secret`
- 加飞书原生 `confirm` 确认弹窗（点击按钮先弹窗再操作）

### 3. 飞书按钮 confirm 弹窗

`build_feed_contest_message` 和 `build_contest_daily_summary_message` 两处忽略按钮均加 confirm 弹窗：
- 标题："不再提醒此赛事"
- 文案："确认后本条赛事将不再出现在未来的推送中。"

### 4. 修正 WEB_BASE_URL 端口

`.222` 的 `.env` 中 `WEB_BASE_URL` 从 `8088` 修正为 `8888`（Nginx 实际端口早已改为 8888，注释写明"8088/8080/8000 已被同机其他项目占用"）。

### 5. 赛事爬取链路排查

**现状**：

| 来源 | 状态 | 说明 |
|------|------|------|
| cnmaker-contest | ✅ 12条 | 创客中国官网正常 |
| cqkjj-contest | ✅ 3条 | 重庆科技局，全是延期通知 |
| wnd-contest | ⚠️ 0条 | 最新大赛通知 2025-06-11（403天前），已超时效 |
| gxt-contest | ⚠️ 0条 | 江苏工信厅文件通知栏目无大赛相关文章 |
| cqjjw-contest | ⚠️ 0条 | 唯一含"大赛"的是入围名单公示，被排除词正确过滤 |

结论：不是爬虫 bug，是真的没有最近的新比赛数据。

### 6. 时效与排除词优化

- `registry.py`：排除词加 `"喜报"` `"佳绩"` `"斩获"`
- `.222` `.env`：`CONTEST_MAX_AGE_DAYS=365`（默认 180→365）
- `contest_service.py`：`_build_discovery_query` 加 `site:gov.cn`

### 7. 全网发现排查

Bing 中文分词把"人工智能"拆成单字"人"+"工"，搜索结果全是汉语词典（"人工的意思"）。`site:gov.cn` 也无效。全网发现功能对中文关键词基本不可用。

---

## 待做

### 今晚/后续

1. **百度搜索 API 接入**（替代 Bing 全网发现）
   - 需要：百度智能云账号 → 开通搜索服务 → 获取 API Key + Secret Key
   - 实现：新建 `BaiduSearchEngine` 实现 `SearchEngine` 接口
   - 每天 100 次免费额度
   - 代码结构可以参考现有的 `BingSearchEngine`

2. **代码已提交 main**，commit：
   - `e0b1659` feat: 每日赛事摘要支持逐条「不再提醒此赛事」+ 免登录签名链接
   - `f467dbe` fix: 赛事爬虫时效放宽 + 全网发现查询优化

3. **`.222` 已部署**，容器运行最新代码

4. **全网发现功能**：暂时保留 Bing，等百度 API 接入后替换

### 环境变量

`.222` `.env` 新增：
```
CONTEST_MAX_AGE_DAYS=365
WEB_BASE_URL=http://118.196.142.222:8888
```

---

## git 状态

```
f467dbe (HEAD -> main, origin/main) fix: 赛事爬虫时效放宽 + 全网发现查询优化
e0b1659 feat: 每日赛事摘要支持逐条「不再提醒此赛事」+ 免登录签名链接
ec2e2b6 Merge pull request #82 from ronvis7/fix/web-discovery-bing-quality
```
