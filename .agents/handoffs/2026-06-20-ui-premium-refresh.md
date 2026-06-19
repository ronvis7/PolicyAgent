# 前端视觉升级——暖调专业·政务信任感

Issue：—
分支：`feat/ui-premium-refresh`（PR #56）+ `feat/ui-chat-view-refresh`（PR #57），均已合并 main
负责人：—
更新时间：2026-06-20

## 目标

现有 UI 偏扁平、缺乏高级感。根因是**设计 token 形同虚设**：`globals.css` 还是 shadcn 默认冷黑白，
但页面全是写死 hex，两套体系并行，且只有单级阴影/单一边框、无 elevation 层次。按用户选定的
「暖调专业·政务信任感」方向，分 3 层从根到叶系统性升级，并把原 Manus 中性灰聊天视图一并收口。

## 已完成

### PR #56（P1 token + P2 组件 + P3 业务页）

- **P1 设计 token 体系**（`globals.css`，地基）：
  - 暖中性底色（`#fafaf9` 底 / `#e7e4df` 边 / `#1c2127` 字）替换 shadcn 默认冷黑白；
    青绿 `#287174` 接入 `--primary`，**Button/Badge/焦点环/选区色自动品牌化**。
  - 新增可复用工具：品牌色阶 `brand-50..700`（`bg-brand-600` 等）、分层阴影
    `shadow-card/hover/pop/modal`（`shadow-[var(--shadow-card)]`）、衬线字体栈 `--font-serif`
    （`font-serif`，系统中文衬线优先 Source Han Serif/Noto Serif/Songti，**零网络、不依赖离线构建拉字体**）。
  - 暗色 `.dark` 同步对齐暖调主色（主色暗下提亮一档），真正可用。
- **P2 核心组件精修**（一次改、处处生效）：
  - `Button`：主按钮分层阴影 + hover 抬升(`-translate-y-px`)/active 下沉 + 品牌色阶 hover。
  - `Dialog`：modal 级阴影 + 加大圆角(`rounded-2xl`) + 遮罩毛玻璃(`backdrop-blur`) + 衬线标题。
  - 侧栏 `left-panel`：active 项 3px 品牌色左指示条 + 主色图标；logo 加品牌色圆点。
- **P3 页面级升级**：落地页（衬线问候 + 主色高亮用户名 + 图标推荐卡）、工作台 Feed
  （卡片类型彩条 + hover 抬升 + 命中度迷你进度条）、公开政策库/资质/数据来源/企业档案/知识库/登录注册
  （标题衬线化、卡片 hover 抬升、强调态统一品牌色、登录注册品牌渐变背景）。

### PR #57（聊天会话视图收口）

- **工具卡片 chip**（`tool-use/tool-badge.tsx`，所有工具卡片共享件，一处改全部生效）：冷灰→暖底 + 主色图标 + 品牌色 hover。
- **用户气泡**：白底裸边 → 品牌暖底 `bg-brand-50` + 圆角 + token 阴影。
- **助手头像/正文、step 块**：文字色拉齐暖中性；step 完成态勾选圈用主色、hover 用品牌色、连接线用 token 边框。
- **会话标题**衬线化；**输入框**容器聚焦光晕(`focus-within` 品牌边框+阴影) + 发送按钮改品牌实心；**聊天头部字标**加品牌色圆点。

## 设计 token 速查（后续开发请优先复用，勿再写死 hex）

| 用途 | 写法 |
|---|---|
| 页面底/卡片/边框/文字 | `bg-background` `bg-card` `border-border` `text-foreground` `text-muted-foreground` |
| 品牌主色 | `bg-primary` `text-primary` `border-primary`；色阶 `bg-brand-50` … `bg-brand-700` |
| 分层阴影 | `shadow-[var(--shadow-card)]`（卡片）/`-hover`（悬浮）/`-pop`（浮层）/`-modal`（弹窗） |
| 衬线标题 | `font-serif`（配 `font-semibold tracking-tight`） |
| 卡片悬浮质感 | `transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-hover)]` |

页面标题统一范式：`font-serif text-lg font-semibold tracking-tight text-[#1c2127]`。

## 接口与迁移

无。纯前端，无 API/Schema/迁移/依赖变化。延续 PR #35/#37 的视觉刷新做法。

## 验证

- 两个 PR 每个 commit 均 `npx tsc --noEmit` 干净、`npx eslint`（改动文件）干净、`npx next build`（12 页）全编译。
- CI 三项（backend / frontend / integration）全绿后才合并。
- 真机走查待做（`.\dev-up.cmd -Mode Remote -Build`：落地页/工作台/登录页/会话页/各弹窗）。

## 未完成 / 刻意未做

- **设置弹窗 `manus-settings.tsx` / 成员面板 `members-setting.tsx`**：PR #35 起有意保留的自成一套灰色主题，
  本轮仍未拉齐（维持其内部一致性）；如要全站统一可后续单独处理。
- `chat-input.tsx:90` 有一条**预存**的 `'error' is defined but never used` eslint 告警（非本轮引入），保持 diff 聚焦未动。
- 真机走查定稿未做。

## 风险

- 衬线标题走**系统字体栈**而非内嵌 webfont：未装中文衬线的环境会回落到系统宋体/serif，质感略降但不破版；
  若要保证一致性可后续用 `next/font` 内嵌（注意离线构建拉字体的网络约束，见 #35 起栈坑记录）。
- 改了 shadcn `--primary` 等语义 token：任何**新写死 hex** 的组件不会自动跟随主题，务必按上表用 token。

## 下一步

1. 真机走查定稿；如需微调主色深浅/圆角/阴影力度/字体，集中反馈一轮。
2. 若整体满意，可择期拉齐设置弹窗/成员面板，完成全站视觉统一最后一块。
