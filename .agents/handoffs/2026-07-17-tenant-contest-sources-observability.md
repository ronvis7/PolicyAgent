# 企业自建赛事来源与全网发现可观测化

## 已实现

- 企业 owner/admin 可通过 `/api/tenant/contest-sources` 创建、预检、启停、删除静态 HTML 赛事来源；配置包含地区、列表 URL、标题关键词、列表链接 CSS 与正文 CSS。
- `TenantContestCrawler` 仅支持公开静态 HTML，拒绝携带凭据、内网 DNS/IP、非 HTML、过大响应和过多重定向；JS 渲染、登录、验证码与 PDF 列表不支持。
- 新增 `contest_runs`，订阅的“立即搜索”和企业来源的“抓取”均保留最近 10 条运行状态与计数，并由服务端执行 5 分钟冷却。
- 企业来源结果以 `origin_type=tenant` 标记，并通过 `tenant_contest_source_items` 关联；赛事列表与详情按当前 tenant 过滤，其他租户不能读取。
- 每日链路已接入企业来源抓取，官方来源后、关键词发现前执行。手动执行不触发订阅通知回调。
- 赛事中心前端已增加“立即搜索 / 记录”和“我的赛事来源”表单；平台官方来源表单可填写地区并列出 `cnmaker/wnd/gxt/cq` 模板。
- 地区表单可直接选择已验证官方来源；若没有预设，可调用 `/api/tenant/contest-sources/suggestions` 让 Agent 搜索公开门户并填入候选配置，但仍必须由管理员创建并预检。
- 全网发现会排除已配置官方来源的域名；页面的赛事筛选与管理数据改为独立加载，管理接口异常不会再中断“全部赛事 / 官方来源 / 全网发现”切换。
- 2026-07-17 修复：Bing 中文网页不再返回旧 `li.b_algo` DOM，导致所有地区建议和全网发现解析为零；`BingSearchEngine` 改为优先解析公开 RSS。地区建议改为“部门门户 → 赛事通知”两阶段搜索。上海市实测可返回上海市政府门户候选。
- 2026-07-17 修复：最近一条赛事 Feed 创建于 2026-07-09，现行“仅新 Feed 即推”语义使后续任务静默；定时赛事管道已重新接入租户级每日状态摘要。未手动发送测试飞书。

## 迁移与验证

- 新迁移：`b1c2d3e4f5a6_tenant_contest_sources_observability.py`，前序为 `a4b5c6d7e8f9`；`c2d3e4f5a6b7_add_tenant_contest_source_preset.py` 后续补充 `preset_source_id`。
- 已通过 `python -m compileall api/app`、迁移文件 `py_compile` 与 UI `npm run build`。本地 Compose 已重建，API/UI healthy，Alembic current/head 均为 `c2d3e4f5a6b7`，并确认数据库已有 `preset_source_id`。
- 使用临时只读管理员令牌验证 `GET /api/tenant/contest-sources` 返回 200；`GET /api/contests` 的全部、`origin=official` 和 `origin=web` 均返回 200。
- 本机 `api/.venv` 引用了已不存在的 uv Python，无法直接运行 pytest；需重新创建该虚拟环境后运行赛事服务定向测试。

## 风险/后续

- 企业来源首次入库仍复用全局 `policies.source_url` 去重；要避免公开列表泄露，常规政策列表与 RAG 后续应继续显式排除 `origin_type=tenant`（赛事中心已经过滤）。
- 每日企业来源的 Feed/飞书通知路径需要在真实租户 Feishu 配置下验收；当前手动路径明确不调用通知钩子。
