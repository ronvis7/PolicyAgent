# 聊天空白 bug 根因排查（MCP 初始化永久悬挂）+ 赛区拓展评估

Issue：—
分支：main（本次仅排查与评估，未改代码）
负责人：—
更新时间：2026-07-08

## 目标

排查"聊天提问后一直无输出、一片空白"的复发 bug 并定位根因；评估"赛区拓展/用户能否在前端自由配置参赛地区"。两项均完成诊断，修复待做。

## 已完成

### A. 聊天空白 bug：根因已定位并在本地 dev 栈复现确认

**现象**：用户问"我的企业最近想要找个比赛参加一下，有合适的吗"，前端永远空白，无 AI 回复也无错误提示。复发性 bug。

**证据链**（2026-07-08，本地 dev 栈连共享库）：

1. 查库：会话 `ad1af4fd-e6a9-4b00-8dda-24f21270565b` 的 `events` 里**只有 1 条用户消息事件**（08:26:05 UTC），无 Plan/Title/AI 消息/Error 事件，状态停在 `pending`——`PlannerReActFlow.invoke` 从未启动（它第一步就会把状态改 RUNNING）。
2. 会话沙箱容器 `policy-sandbox-d20c51ea` 08:26 正常创建、supervisor 探活 200——`ensure_sandbox` 没问题。
3. 容器内实测（模拟 `AgentTaskRunner.invoke` 的启动序列）：用当前 `config.yaml` 的完整 mcp_config 跑 `MCPTool.initialize()`，**120 秒超时不返回**；只连 `jina-mcp-server` 则 **0.9 秒成功**（21 个工具）。

**根因**（三层叠加）：

1. `api/config.yaml`（gitignored 运行时文件）配了 `amap-maps-streamableHTTP`（占位 key，`enabled: false`）。
2. **enabled 从未被过滤**：`app/interfaces/service_dependencies.py`（`get_agent_service` 处 `mcp_config=app_config.mcp_config`）把整份配置原样传入；`MCPClientManager._connect_mcp_servers` 注释称"enabled 筛选在外部执行"，但代码里没有任何地方筛——**disabled 的 server 也会连**。
3. **无超时 + SDK 悬挂**：高德对无效 key 返回自家 REST 错误 JSON（HTTP 200、非 JSON-RPC，`infocode: 10001`），MCP SDK `streamable_http` 解析失败后 `session.initialize()` 永远等不到合法响应；连接无 `asyncio.wait_for` 兜底 → `AgentTaskRunner.invoke` 卡死在 `self._mcp_tool.initialize()`，永不到达流程/LLM，也不产生 ErrorEvent → 前端空白。**每次新建聊天任务必现**（新会话、或会话空闲后再发消息都会新建任务）。

**帮凶（排查盲点，建议随修）**：应用 `app.*` 日志全被吞——启动时 alembic `fileConfig`（`disable_existing_loggers` 默认 True）把已导入模块的 logger 禁掉，stdout 只剩 sqlalchemy echo；本次只能靠查库定位。这就是 STATUS"app 日志输出到 stdout"待办的真相。

### B. 赛区拓展评估：现状为刻意设计，拓展=加爬虫源

- 档案页「参赛关注地区」是 chips 多选（`ui/src/app/enterprise-profile/page.tsx` 的 `ContestRegionPicker`），**选项动态 = 已注册赛事爬虫源（item_type=competition）的 region 去重**（PR #66 设计）。当前仅三个：江苏省无锡市新吴区（wnd-contest）/ 江苏省（gxt-contest）/ 重庆市（cqkjj·cqjjw-contest）。
- 不开放自由输入的原因：地区只是过滤器，数据来自逐个逆向的政府门户爬虫；自由填"浙江省"没有对应数据源 → 分栏永远为空，体验更糟。
- 拓展路径（按成本）：
  1. **低**：`CqPolicyCrawler` 已按 base_url+column_path 参数化，凡 TRS WCM 建站的委办局/地市栏目注册一条配置即可，前端选项自动出现；
  2. **中**：其他省市门户逐个逆向，已有三套 CMS 模板可复用（Hanweb dataproxy / TRS WCM / 东网）；每个门户先做可逆向性甄别（教训：江苏科技厅 kjt 被 WAF 挡死，勿再试）；
  3. **可选 UI 层**：选项改全国省级列表、未覆盖标"暂无数据来源"——仅预期管理不产生数据，不推荐单独做。

## 接口与迁移

- 本次零改动（纯排查）。修复也预计零迁移、零新增依赖。

## 验证

- `docker exec policy-api python /tmp/probe_mcp.py`：完整 mcp_config init 120s TIMED OUT（stdout 可见高德 `infocode: 10001` 的 JSON-RPC 解析失败 traceback）。
- `docker exec policy-api python /tmp/probe_jina.py`：仅 jina init OK in 0.9s、21 tools。
- 查库脚本确认会话仅 1 条用户消息事件、状态 pending（脚本临时文件，未入库）。

## 未完成

1. **止血（免代码，最快恢复聊天）**：从 `api/config.yaml` 删掉 `amap-maps-streamableHTTP` 整个条目（注意：`enabled: false` 当前无效，必须删）→ 重启 policy-api（或 `.\dev-up.cmd -Mode Remote -Build`）。jina 条目可留（init 正常；其工具实际调用因占位 key 会失败，Agent 侧有 ToolResult 失败兜底）。
2. **修复 PR**（`app/domain/services/tools/mcp.py` + `app/interfaces/service_dependencies.py`）：
   a) 连接前按 `enabled` 过滤（补上"外部筛选"缺失的另一半）；
   b) 每个 server 连接包 `asyncio.wait_for`（建议 ~20s；注意 anyio cancel scope 跨 task 退出会抛 RuntimeError，`cleanup()` 已有防御，超时路径需同样兜底）；
   c) MCP/A2A 初始化整体 best-effort：失败/超时记日志跳过，不阻塞聊天主链路。
3. **日志修复**：让 alembic 迁移的 logging 配置不再禁用应用 logger（`fileConfig(..., disable_existing_loggers=False)` 或调整启动顺序），否则线上问题永远盲查。
4. **赛区拓展**：待用户给出优先省市清单 → 先做门户可逆向性甄别 → 通过者排爬虫 PR。

## 风险

- 修复前**所有新建聊天任务都会空白悬挂**（含 .222 线上，若其 config.yaml 也带占位 amap 条目——部署时须核对服务器同目录 config.yaml）。
- `config.yaml` 是 gitignored 运行时文件，修代码不等于修环境：每台机器/服务器的存量占位条目要各自清理。
- MCP 超时包装需在同一 asyncio Task 内进出 anyio cancel scope，实现时注意（同 `_cleanup_tools` 的既有注释）。

## 下一步

1. 执行"未完成 1"止血并真机验证聊天恢复，然后按"未完成 2"开修复分支（建议 `fix/mcp-init-hang`）。
