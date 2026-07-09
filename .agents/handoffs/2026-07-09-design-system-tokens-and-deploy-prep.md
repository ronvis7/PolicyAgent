# 全站设计系统 token 化 + .222 部署准备（含未决时间筛选 + 部署 runbook）

Issue：—
分支：`feat/design-system-tokens`（PR #79，**已合并 main** `00c00a9`）
负责人：—
更新时间：2026-07-09（傍晚收工，晚上继续）

## 目标

用户要求"按 DESIGN.md 那套整体刷一遍"前端 + 修"时间筛选默认 24/25 年"，之后全量部署到 .222。
本轮完成 token 化并合并；时间筛选定位未果（无对应控件）；部署应用户要求先按下（先做完 UI）。

## 已完成

### A. 全站设计系统 token 化（PR #79，纯前端，已合并 main）

- **背景**：`ui/src/app/globals.css` 早已具备 DESIGN.md 整套 token（暖中性画布/青绿主色 #287174/
  衬线 `--font-serif`/分层阴影 `--shadow-*`/暗色对齐，#56/#57 建），但各页此后大量写死 hex——既
  不一致，**暗色模式在这些页失效**（写死浅色不跟随主题）。
- **改动**：脚本化把中性 hex 换 token（`scratchpad/tokenize.py` 一次性工具，已丢弃）：
  背景/表面→`bg-background`/`bg-card`/`bg-muted`/`bg-accent`/`bg-sidebar`；边框→`border-border`；
  墨黑文字→`text-foreground`；次要文字→`text-muted-foreground`；主色→`text-primary`/`bg-primary`；
  旧 arbitrary 阴影→`shadow-[var(--shadow-card)]`；`bg-white`→`bg-card`；登录/注册渐变改主题感知
  `from-muted via-background to-accent`。**11 页 + 共享组件共 427 处替换**。
- **刻意保留**：语义状态色（琥珀截止/紫赛事/翠资质/红校验，DESIGN.md 明确保留）；对话框遮罩
  恢复固定深色 `bg-[#1c2127]/45`（scrim 须两主题皆深，不能用会翻白的 foreground）。
- **入库** `ui/DESIGN.md`（设计系统真源镜像，version alpha）。
- **验证**：`tsc --noEmit` + `eslint`(0 error) + `next build` 全绿。**纯 token 替换、零逻辑/接口改动**。
- **后续开发铁律**：优先用 token，勿再写死 hex。

## 未完成 / 待办（晚上继续）

1. **PR #79 视觉真机走查未做**：token 替换语义安全且构建通过，但视觉需在 dev 眼看一遍（尤其
   **暗色模式**是否处处跟随）。若某页看着不对，多半是 token 角色映射的边界个例，易微调。
2. **`knowledge/[id]` 代码/Markdown 预览页未 token 化**：它有独立深色调色板（#525252/#303030/
   #1e1e1e 等成套灰阶），盲替风险高，本轮**排除**，留单独处理。
3. **时间筛选 #2 未修——定位未果**：用户反馈"公开政策/赛事时间筛选默认取到 24/25 年"，但
   **遍历整个 UI 无任何时间/日期筛选控件**（`/policies` 只有地区/部门/关键词三个筛选）。三种可能：
   ①看到的是列表数据本身就是 2024/2025（真实发布日期，按发布日期倒序，非筛选 bug）；②另有我
   没找到的控件；③其实是想**新增**一个时间筛选并给合理默认。**待用户指认在哪个页面/哪个控件**
   看到该默认，再动手，勿猜。
4. **参赛关注地区 chips 拥挤 #1**（更早 handoff 提的另一 UI 项）仍未做。

## 部署准备（.222 全量部署 —— 应用户要求先按下，UI 完再上）

用户已授权"所有服务都上服务器"，但发现 UI 未调，遂暂停部署、先做 UI。晚上 UI 收尾后再部署。
**部署 runbook（已验证，见记忆 `server-deployment`）**：

- **代码位置**：服务器 `/root/policy_manus`（`git archive` 打包 scp 上送，无 .git）。
- **SSH**：必须 `-i ~/.ssh/id_ed25519_policy_manus`（config 只配 user 未配 IdentityFile）。
- **传输**：`git archive main --format=tar | ssh -i <key> root@118.196.142.222 'tar -x -C /root/policy_manus'`，
  **走 Git Bash**（PowerShell 会损坏二进制 tar）。运行时文件 `.env`/`api/config.yaml`/
  `docker-compose.server.yml` 在包外、原样保留。
  ⚠️ **Claude Code 安全分类器常拦这条"批量代码树→生产机"命令**，需用户 `!` 自跑或加放行规则。
- **启动**：`cd /root/policy_manus && docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --build`。
- **迁移自动落库**：本轮新 head `f3a4b5c6d7e8`（`source_crawl_states` 表，纯新增）随 api 启动 upgrade。
- **本次要一次带上的**：#70/#72/#74~#79 全部（.222 仍停在 `15b4ac3`=#64~#69）。
- **两个 server 端 gitignored 文件须手动处理**（部署不覆盖）：
  1. **`api/config.yaml` 高德 amap key**：.222 仍是占位 key → 聊天会悬挂空白（07-08 handoff 根因）。
     须把 amap 条目换真 key + `enabled: true`（本地已这么修好、聊天已通）。
  2. **`.env` 加 `WEB_BASE_URL=http://118.196.142.222:8088`**：飞书赛事卡片「打开工作台」按钮才出
     （#75）；不配也能正常推送，只是没按钮。
- **部署前读一次性巡检**（只读 SSH 不被拦）：`docker ps`、`docker exec policy-api alembic current`、
  `grep -A3 amap /root/policy_manus/api/config.yaml`、`grep WEB_BASE_URL .env`。

## 风险

- PR #79 视觉未真机确认（纯 token 替换、构建绿，风险低但需眼看）。
- 部署那条 `git archive|ssh tar -x` 大概率被安全分类器拦，需用户 `!` 自跑。
- 部署后聊天若仍空白 = 服务器 config.yaml amap 仍占位 key（见待办部署项 1）。

## 下一步（晚上）

1. dev 眼看 PR #79（暗色模式）；有问题微调。
2. 用户指认时间筛选 #2 的位置 → 修或确认非 bug。
3.（可选）knowledge/[id] token 化、参赛地区 chips 拥挤 #1。
4. UI 收尾后全量部署 .222：git archive→scp→`up -d --build`（用户 `!` 自跑传输）+ 改 server
   `config.yaml` 高德 key + `.env` 加 `WEB_BASE_URL`，验证公网 8088 + 聊天 + 飞书按钮。

## 续接：核心三页结构重构（2026-07-09 晚）

分支：`feat/core-ui-restructure`（基于 `main` `00c00a9`，未提交/未开 PR）

用户确认 #79 肉眼变化不明显后，本轮补做真正的页面结构重构，保持 API 与业务逻辑不变：

- **工作台 `/feed`**：改为“机会雷达”结构；新增全部机会/新匹配/14 天内截止/赛事机会四项概览，
  类型与状态筛选合并为统一工具栏，机会卡片改为更克制的数据密集布局；赛事地区卡片去紫色、统一品牌色。
- **公开政策库 `/policies`**：改为“政策资料馆 + 右侧阅读台”；新增编辑体大标题和结果总数，检索区收口，
  列表由卡片套卡片改为带分隔线的文档目录，右侧详情强化原文审阅层级。
- **企业档案 `/enterprise-profile`**：改为企业身份页；企业信息与档案完整度组成主 Hero，下方两栏展示能力标签
  与经营指标；8 项指标按 4×2 网格展示。编辑态字段、权限和保存逻辑不变。

验证：

- `npm.cmd exec tsc -- --noEmit`：通过。
- `npm.cmd run lint`：0 error；30 个仓库既有 warning，本轮三个页面无新增 warning。
- `npm.cmd run build`：通过，14/14 页面生成成功。
- 使用隔离浏览器 + 演示 API 数据完成 `/feed`、`/policies`、`/enterprise-profile` 桌面亮色、强制暗色、
  390px 手机宽度走查；另检查企业档案编辑态。走查中发现并修复经营指标 3 列造成尾部空格的问题。

未做：

- 尚未提交、推送或开 PR。
- 尚未部署 `.222`。
- “时间筛选默认 24/25 年”仍缺少具体页面/控件定位。
