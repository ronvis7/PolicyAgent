# 企业档案查看态打磨 + 上海杨浦区政策来源

Issue：无
分支：`feat/yangpu-source-and-profile-view` → **PR #37 已合并 main（2026-06-17），分支已删**
更新时间：2026-06-17（合并后回填）

## 背景 / 目标

本轮不做新功能，打磨现有两处体验（用户提出）：
1. **企业档案页**本质是展示企业信息，但即使填好也永远是一整页灰色禁用表单，体验差。
2. **公开政策库地区切换**只有"无锡新吴区/全部"，想真正切到别的地区（用户举例上海杨浦区）。

第①是纯前端查看/编辑分态；第②按既有"通用多区域框架"——加一个地区＝实现一个爬虫 + 注册一条来源
（见 handoff `2026-06-15-multi-region-policies`）。决策前先调研杨浦区门户可抓性（①b 教训：勿假设可抓）。

## 已完成

### ① 企业档案查看/编辑双态（纯前端，无接口/迁移）
`ui/src/app/enterprise-profile/page.tsx` 重写为 `mode: 'view' | 'edit'`：
- **默认查看态 = 企业名片**：Hero 卡（企业名 + 省/市/区面包屑 + 行业/规模徽章 + 最后更新）、
  **档案完整度进度条**（`completeness()` 按 15 个对下游匹配/资质差距有意义的字段加权，省市区有默认值不计）、
  主营业务、资质/技术域/关键词**标签云**（`TagCloud` 只读，空弱化"未填写"）、
  经营研发 8 指标 + 成立日期**数据卡网格**（`MetricCard`，未填显 `—`，区分"未填写≠0"）。
- owner/admin 右上角「编辑」→ 切 `EditForm`（沿用原分区字段，绑 `draft`）；**取消放弃改动、保存提交后切回查看态**。
- member 只读看名片；空档案（无 `company_name`）走 `EmptyState` 引导页（owner/admin 显「开始填写」）。
- 门禁：`tsc --noEmit` + `eslint` 该文件全绿。

### ② 上海杨浦区政策来源（后端，永久来源、非一次性）
**逆向结论（2026-06-17，公网可直连、无鉴权）**：杨浦区门户 `www.shyp.gov.cn` 是东网(easttone)政务云 CMS。
- 列表：同源 ES 接口 `POST /front/api/data/search`，body `{"channelList":["1899"],"pageNo":N,"pageSize":N,"orderFields":["display_date","id"],"orderTypes":["desc","desc"]}`。
  **关键坑**：`channelList` 必须传**数组**（传字符串/`channelIds` 会被忽略而返回全站 1 万条；数组 `["1899"]` → 1463 条真正的"政府文件"）。
  返回 `data.totalPage` + `data.list[]`（`title`/`url` 全链接/`dispatch_agency` 发文机关/`display_date` 毫秒时间戳）。
- 详情：服务端直出静态 HTML，正文 `div#ivs_content`(class `Article_content`)，文号/索引号在「`<span>发文字号：</span><span>值</span>`」结构。
- 栏目 id `1899`=「政府文件」，逆向自 `/zhengwu/zwgk-zfwj/` 页面内联 `new CMS('#columnlist',{ids:'1899',http:'/front/api/data/search'...})`。

代码：
- 新增 `api/app/infrastructure/external/crawler/shyp_policy_crawler.py::ShypPolicyCrawler`：纯解析（`_parse_list_payload`/`_parse_detail`/`_parse_publish_date_ms` 毫秒→date/`_meta_value` 取 span 对）与网络 I/O 分离，限速 0.8s、详情失败容错跳过、不下载附件。
- `registry.py` 注册 `CrawlerSource(key="shyp", name="上海杨浦区门户·政府文件", region="上海市杨浦区", factory=ShypPolicyCrawler)`。
- 入库编排/端点**零改动**（按 source 选择爬虫的框架已就绪）；前端地区下拉/抓取来源下拉**零改动**自动出现"上海市杨浦区"。
- `core/config.py`：`POLICY_RECRAWL_SOURCES` 默认值 `wnd-apply` → `wnd-apply,shyp`，杨浦区随无锡 04:00 一同定时重爬保鲜（调度器零改动，`policy_recrawl_source_list` 按逗号切分）。

### ③ 公开政策库抓取反馈（纯前端，`ui/src/app/policies/page.tsx`）
抓取端点是 fire-and-forget `BackgroundTasks`（约 1-2 分钟），原前端 POST 一返回就 `setIngesting(false)`，按钮转圈瞬停像"秒完成"、无完成信号、需手动猜时机刷新（用户实测踩到："以为没工作"）。
- 抓取中保持按钮 loading + 文案"抓取中…"，整个后台窗口持续；新增顶部琥珀色横幅"正在后台抓取「X」…约 1-2 分钟，完成后自动刷新"。
- 固定 `INGEST_WINDOW_MS=90_000`（落在后端 1-2 分钟区间）后自动刷新列表 + toast 收尾；卸载清理定时器防卸载后 setState。
- toast 文案对齐后端"约 1-2 分钟"，弃用模糊的"稍后"。
- **注**：仍是定时窗口的近似反馈，非真实进度；要精确进度需后端 job 状态表/端点（本轮按"纯前端轻量修"档位决策，不动后端）。

## 接口
- 无新表、无迁移、无新端点。`alembic head` 不变（`a8b9c0d1e2f3`）。
- 既有 `GET /policies/sources` 自动多一条 `shyp`；`POST /policies/ingest?source=shyp` 可抓该来源；`GET /policies?region=上海市杨浦区` 筛选。

## 验证
- 新增 `tests/app/infrastructure/external/test_shyp_policy_crawler.py` 9 条解析单测（字段映射/跳脏数据/issuer 回退/channelList 数组/分页/正文+文号+索引/缺字段/毫秒日期/占位短横）。
- **全量 `pytest tests/app` 182 passed**，唯一 1 error 为既有需真库的 `test_get_status`（与历史一致）；`import app.main` OK；registry 列出 `wnd/wnd-apply/shyp`。
- **真机实跑验证**（直连源站抓 1 页 4 篇）：标题/发文机关/日期/文号/索引号解析正确，正文 2952/3205/260/6956 字均完整（含《支持打造OPC超级个体社区若干措施》《安全生产举报奖励办法》等真实政府文件）。
- 前端 `tsc`/`eslint`（改动文件）绿。
- ruff/black 本机 venv 未装（CI 仅 compile + 跑 tests），未跑格式化。

## 收尾状态（本轮已闭环）
1. ✅ **真机入库走查**：连 .222 跑 `ingest(source=shyp)`，杨浦区数据落库、`/policies?region=上海市杨浦区` 可见、列表/正文/文号/索引号正确（含向量双写进公开库）。
2. ✅ **定时重爬已加**：`shyp` 进 `POLICY_RECRAWL_SOURCES` 默认值，随无锡 04:00 跑。
3. ✅ **已提交并合并**：PR #37（CI backend+frontend 双绿）合并 main，分支已删。

## 下一步 / 遗留观察项（非阻塞，用户回来再定）
1. **杨浦区栏目噪音**：`1899`"政府文件"含部分非惠企公文（请示、统计法转载等），与无锡同粒度。本轮决策**先上线观察**；真有噪音再在 catalog/匹配侧做聚焦过滤，或换更细栏目 id（逆向同法）。
2. **抓取真实进度**：当前是 90s 定时窗口的近似反馈；若要精确进度/完成通知，需后端 job 状态表 + 轮询或 SSE（本轮按"纯前端轻量修"档位明确不做）。
3. **历史回填**：手动抓取写死 `max_pages=3`（最新约 60 条保鲜）；杨浦区有 1463 条，要回填得走 API 把 `max_pages` 调大（最大 20），前端未暴露该参数。

## 风险 / 注记
- 杨浦区"政府文件"栏目含部分非企业政策类公文（如请示、统计法转载），与无锡同属"政府文件"粒度；如需更聚焦"惠企政策"，后续可在 catalog/匹配侧过滤，或换更细栏目 id（逆向同法）。
- 列表偶有同一文档挂多个栏目 URL（同 id 不同 path）；入库按 `source_url` 去重，内容可能重复，规模化时再观察。
- 抓取走 API 进程内（复用其 DB/embed 连接），主机直跑因 SSH 隧道只对容器生效会连不上（同 wnd）。
