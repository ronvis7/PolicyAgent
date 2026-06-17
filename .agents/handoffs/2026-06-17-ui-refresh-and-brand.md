# 前端视觉统一 + 品牌收尾（采纳同事 ui 分支）

Issue：—
分支：`feat/ui-refresh`（PR #35，已合并 main）
负责人：—
更新时间：2026-06-17

## 目标

采纳同事 `ui` 分支（政策库/知识库页刷新）为基线，把其余页面拉齐到同一套视觉语言，
统一品牌。验收：核心页面观感一致、品牌无 Manus 残留、tsc/eslint/build 全过、真机起栈确认本版定稿。

## 已完成

- **采纳同事 `ui` 分支**（原始 commit `7737119`）：`/policies` FiscalNote 式检索工作台、
  `/knowledge` 文档库卡片首页 + 图谱预留、`left-panel` 分组导航 + 品牌徽标 + 当前企业主体卡片。
  知识库页预留功能（Neo4j 图谱、文件夹、KB 类型卡 Chroma/Milvus/LightRAG、原文预览）
  **按产品决定保留作路线图展示**（仅前端交互/预留入口，点击给"暂未接入"提示）。
- **视觉拉齐**（设计 token：圆角白卡片 `#fff`/`#e5e2de` 边、`#f8f8f7` 底、青绿强调 `#287174`、
  统一带副标题 header、柔和阴影 `shadow-[0_10px_30px_rgba(16,24,40,.04)]`）：
  工作台 Feed（`feed/page.tsx`）、资质机会（`qualifications/page.tsx`）、企业档案
  （`enterprise-profile/page.tsx`）、登录/注册（`login`/`register/page.tsx`）。
- **修复企业档案分区标题位置异常**：`FieldLegend` 渲染 `<legend>`，会吸附 `<fieldset>` 边框、
  跳出 padding；改由外层 `div` 承载卡片样式（抽 `CARD_CLASS` 常量复用），标题回到卡片内部。
- **品牌收尾**：落地页问候改真实 `user.display_name`（原**硬编码 `Ronvis9`**，是 bug）；
  `chat-header` 空白 logo 占位 → `PolicyManus` 字标；助手头像 manus 字样 SVG（`manus-icon.tsx`）
  → `PolicyManus` 文字字标（随父级 `currentColor` 灰/红变色）；落地页推荐问题（`config/app.config.ts`）
  由 Manus 演示文案（埃菲尔铁塔/GitHub/外卖大战）换成贴合产品（资质匹配/差距/政策检索）。

## 接口与迁移

无。纯前端，无 API/Schema/迁移/依赖变化。

## 验证

- `npx tsc --noEmit` ✅；`npx eslint`（改动文件）✅；`npm run build`（11 页全编译）✅。
- 全栈 Remote 真机起栈（连 .222）：`http://127.0.0.1:8888` 新 UI 正常，用户确认本版定稿。

## 未完成

- 设置弹窗 `manus-settings.tsx`、成员面板 `members-setting.tsx` 自成一套灰色主题，本次**有意保留**
  以维持其内部一致性；如要全站统一可后续单独处理。
- 聊天会话视图（`session-detail-view`/`chat-message`/工具卡片 `tool-use/*`）仅动了 `session-header`
  标题色，整体仍是原 Manus 聊天 UI 的中性灰，未深度拉齐。

## 风险

- **起栈坑（非代码问题）**：远程库走 SSH 隧道冷启动慢，api 在 healthcheck `start_period`(120s) 内
  常来不及 healthy，`docker compose up` 会提前判失败退出（连带 ui 停在 Created、nginx 因 ui 未起
  DNS 解析失败崩溃重启）；但容器 `restart: unless-stopped` 仍在跑，api 约 10–15 分钟后才真正 healthy。
  解法：api healthy 后手动 `docker compose -f docker-compose.yml -f docker-compose.remote-db.yml
  up -d --no-deps policy-ui policy-nginx` 再 `restart policy-nginx`。
  **建议后续修**：api healthcheck `start_period` 调到 ~300s；nginx 加 `depends_on: policy-ui`(healthy)。
- 知识库预留功能是"路线图展示"，点击不可用——对外演示需说明，避免被当成已交付能力。

## 下一步

1. 若要继续打磨，优先聊天会话视图与设置弹窗的视觉统一。
2. 回到产品主链路待办（见 STATUS「当前最高优先级」：多区域申报源 / PDF 附件解析 / banded 条件模型）。
