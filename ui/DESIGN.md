---
version: alpha
name: ZhengXun-Agent-design-system
description: >
  政讯 Agent（面向中国企业的政策咨询 Agent）的设计系统。一套「政务信任 + 编辑体阅读」的暖调界面：
  暖中性画布（{colors.canvas}）配青绿品牌主色（{colors.primary}），衬线 display 标题（weight 400、
  紧行高、负字距）营造政务权威与可信，humanist sans 正文承载政策长文与聊天可读性。几何取 Notion 的
  sober-editorial（8px 按钮、12px 卡片，绝不用全圆角按钮），阅读排版取 Claude 的暖画布 + 衬线标题，
  数据密集列表（情报 feed / 资质 / 赛事）借 Linear 的精确间距与克制。原生支持明暗双主题。
  产品界面覆盖：agentic 聊天单窗口、政策原文详情、知识库管理、情报 feed、资质与赛事列表、企业档案、会话历史。

# ===========================================================================
# 唯一真源说明：以下 token 与 ui/src/app/globals.css 完全对齐。
# 改设计先改 globals.css，再同步本文件；不要在这里发明新色值。
# ===========================================================================

colors:
  # 品牌主色（青绿，按钮/链接/焦点环统一走它；亮色 500，暗色提亮到 400）
  primary: "#287174"           # brand-500，亮色主色 / --primary
  primary-hover: "#1f5c5e"     # brand-600，hover / pressed
  primary-deep: "#16484a"      # brand-700，accent 文字 / 强调
  primary-bright: "#4a9d92"    # brand-400，暗色主色 / --primary(dark)
  on-primary: "#ffffff"

  # 品牌色阶（由主色扩展，用于图表、进度、强调背景）
  brand-50: "#eaf3f2"
  brand-100: "#cfe3e2"
  brand-200: "#a9cecf"
  brand-300: "#7fb4b4"
  brand-400: "#4a9d92"
  brand-500: "#287174"
  brand-600: "#1f5c5e"
  brand-700: "#16484a"

  # 暖中性画布与表面（替换纯白/冷灰，建立政务暖调基底）
  canvas: "#fafaf9"            # --background，页面底
  surface: "#ffffff"          # --card / --popover，卡片面
  surface-soft: "#f4f3f1"     # --secondary / --muted，次级面
  accent-surface: "#eaf3f2"   # --accent，极淡品牌色 hover 面
  sidebar: "#ecebea"          # 侧栏暖灰
  hairline: "#e7e4df"         # --border / --input，1px 分隔线

  # 文字（暖墨黑，非纯黑）
  ink: "#1c2127"              # --foreground，主标题 / 正文
  ink-secondary: "#3d4350"    # 次级文字
  muted: "#8a8f99"            # --muted-foreground，三级 / 占位
  accent-ink: "#16484a"       # --accent-foreground，品牌色态文字

  # 语义色（围绕暖调，克制）
  success: "#287174"          # 复用品牌青绿表示"进行中/有效/在报名期"
  warning: "#d9a441"          # chart-3，暖琥珀，中优先级 / 临近截止
  error: "#c0392b"            # --destructive，校验错误 / 已过期
  info: "#4a9d92"

  # 图表 / 数据色阶（围绕主色铺开，暖调和谐）
  chart-1: "#287174"
  chart-2: "#4a9d92"
  chart-3: "#d9a441"
  chart-4: "#6b7280"
  chart-5: "#b45c4b"

  # 暗色（墨黑略带暖意，非纯黑，配青绿高光；对应 .dark 段）
  dark-canvas: "#16181c"
  dark-surface: "#1e2125"
  dark-surface-soft: "#2a2e33"
  dark-accent-surface: "#243433"
  dark-sidebar: "#1a1d21"
  dark-hairline: "rgba(255,255,255,0.10)"
  dark-ink: "#f3f2ef"
  dark-muted: "#9aa0aa"
  dark-accent-ink: "#8fd3c8"

typography:
  # display / 标题：衬线（政务信任感），weight 400，紧行高，负字距（借 Claude 阅读体）
  # 字体栈优先系统已装中文衬线，零网络：见 --font-serif
  display-xl:
    fontFamily: "var(--font-serif)"   # Source Han Serif SC, Noto Serif SC, Songti SC, STSong, SimSun, ui-serif, Georgia, serif
    fontSize: 48px
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: -0.5px
  display-lg:
    fontFamily: "var(--font-serif)"
    fontSize: 36px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: -0.3px
  display-md:
    fontFamily: "var(--font-serif)"
    fontSize: 28px
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: -0.2px
  # title：正文无衬线（sans），用于卡片标题、区块标题
  title-lg:
    fontFamily: "sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.3
  title-md:
    fontFamily: "sans-serif"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
  title-sm:
    fontFamily: "sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.45
  # body：generous leading，承载政策长文与聊天气泡的可读性
  body-lg:
    fontFamily: "sans-serif"
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.7        # 政策原文阅读，行高放宽
  body-md:
    fontFamily: "sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: "sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
  caption:
    fontFamily: "sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
  micro-uppercase:
    fontFamily: "sans-serif"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.5px    # 中文不做 uppercase，仅英文/编号 eyebrow
  button:
    fontFamily: "sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.3
  # mono：政策编号、金额、来源引用、代码/工具调用
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5

rounded:
  xs: 4px      # tag chips
  sm: 6px      # 小徽章、输入内联
  md: 8px      # 按钮、输入框（Notion sober 几何，按钮不用全圆角）
  lg: 12px     # 卡片（= --radius 0.75rem）
  xl: 16px     # 大面板、模态
  xxl: 20px
  full: 9999px # 仅 pill tab / 状态徽章 / 头像

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 32px
  section-sm: 48px
  section: 64px

shadows:
  # 分层阴影 = 高级感核心，对应 globals.css 的 --shadow-*
  card: "0 2px 8px rgba(28,33,39,0.05)"      # 静置卡片
  hover: "0 8px 24px rgba(28,33,39,0.07)"    # hover 抬升
  pop: "0 16px 40px rgba(28,33,39,0.10)"     # 下拉 / 气泡 / popover
  modal: "0 24px 60px rgba(28,33,39,0.14)"   # 模态 / 对话框

components:
  # ---- 按钮 ----
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
    hover: "背景转 {colors.primary-hover}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    border: "1px solid {colors.hairline}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
    hover: "背景转 {colors.surface-soft}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    hover: "背景转 {colors.accent-surface}，文字转 {colors.accent-ink}"
  button-destructive:
    backgroundColor: "{colors.error}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "10px 18px"
  icon-button:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
    padding: "8px"
    hover: "背景 {colors.surface-soft}，文字 {colors.ink}"

  # ---- 卡片 / 容器 ----
  card-base:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "{spacing.xl}"
    border: "1px solid {colors.hairline}"
    shadow: "{shadows.card}"
  card-interactive:              # feed / 资质 / 赛事列表项，可点击
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    border: "1px solid {colors.hairline}"
    shadow: "{shadows.card}"
    hover: "shadow 转 {shadows.hover}，border 转 {colors.brand-200}"
  card-accent:                   # 强调卡（高匹配政策 / 临近截止机会）
    backgroundColor: "{colors.accent-surface}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    border: "1px solid {colors.brand-100}"
  policy-doc-surface:            # 政策原文阅读容器
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-lg}"
    rounded: "{rounded.lg}"
    padding: "{spacing.section-sm} {spacing.xxl}"   # 阅读用大内边距
    maxWidth: "720px"            # 阅读行宽上限，护眼

  # ---- 输入 / 表单 ----
  text-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
    border: "1px solid {colors.hairline}"
    height: "40px"
    focus: "border 转 2px solid {colors.primary}，ring {colors.primary}"
  chat-composer:                 # agentic 聊天输入框（单窗口主交互）
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xl}"
    padding: "{spacing.md}"
    border: "1px solid {colors.hairline}"
    shadow: "{shadows.card}"
    focus: "border 转 {colors.primary}，shadow 转 {shadows.hover}"
  search-input:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "40px"
    border: "1px solid transparent"

  # ---- 聊天 / Agent（核心交互）----
  chat-bubble-user:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm} {spacing.md}"
  chat-bubble-agent:
    backgroundColor: "transparent"     # agent 回答走全宽阅读排版，非气泡
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    padding: "{spacing.sm} 0"
  tool-use-block:                # 工具调用 / agentic 检索过程展示
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.mono}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
    border: "1px solid {colors.hairline}"
  citation-chip:                 # 来源引用（RAG / 档案逐字段来源）
    backgroundColor: "{colors.accent-surface}"
    textColor: "{colors.accent-ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: "1px 6px"
    border: "1px solid {colors.brand-100}"

  # ---- 徽章 / 状态 ----
  badge-status-active:           # 在报名期 / 有效 / 进行中
    backgroundColor: "{colors.accent-surface}"
    textColor: "{colors.primary-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "3px 10px"
  badge-status-warning:          # 临近截止
    backgroundColor: "#fbf1dc"
    textColor: "#8a6516"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "3px 10px"
  badge-status-expired:          # 已过期 / 已截止
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "3px 10px"
  tag-chip:                      # 政策领域 / 地区 / 类型标签
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.caption}"
    rounded: "{rounded.xs}"
    padding: "2px 8px"

  # ---- 导航 ----
  sidebar-region:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.ink-secondary}"
    borderRight: "1px solid {colors.hairline}"
    padding: "{spacing.md}"
  sidebar-nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    hover: "背景 {colors.surface}"
  sidebar-nav-item-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary-deep}"
    borderLeft: "2px solid {colors.primary}"    # 或整块高亮，二选一
    typography: "{typography.label}"
  pill-tab:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "6px 14px"
    border: "1px solid {colors.hairline}"
  pill-tab-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    border: "1px solid {colors.primary}"

  # ---- 数据密集（feed / 资质 / 赛事表格，借 Linear 精确克制）----
  data-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    border: "1px solid {colors.hairline}"
  data-table-row:
    padding: "{spacing.sm} {spacing.md}"
    borderBottom: "1px solid {colors.hairline}"
    hover: "背景 {colors.surface-soft}"
  stat-tile:                     # KPI / 概览数字块
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
    border: "1px solid {colors.hairline}"
    shadow: "{shadows.card}"

  # ---- 反馈 ----
  modal:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xl}"
    padding: "{spacing.xl}"
    shadow: "{shadows.modal}"
    border: "1px solid {colors.hairline}"
  popover:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "{spacing.xs}"
    shadow: "{shadows.pop}"
    border: "1px solid {colors.hairline}"
  toast:                         # sonner
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm} {spacing.md}"
    shadow: "{shadows.pop}"
    border: "1px solid {colors.hairline}"
---

## 概述

政讯 Agent 是面向中国企业的政策咨询 Agent。界面气质是 **「政务信任 + 编辑体阅读」**:用暖中性画布 + 青绿品牌主色替代大多数 AI 产品的冷蓝/冷灰,用**衬线 display 标题**传达政务权威与可信,用宽松行高的无衬线正文承载政策长文与聊天的可读性。整体几何取 Notion 的 sober-editorial(8px 按钮、12px 卡片,**绝不用全圆角按钮**);阅读排版取 Claude 的暖画布 + 衬线标题;数据密集的情报列表(feed / 资质 / 赛事)借 Linear 的精确间距与克制。

**核心气质:**
- 暖中性画布 `{colors.canvas}`(#fafaf9),非纯白冷灰 —— 政务暖调基底
- 青绿品牌主色 `{colors.primary}`(#287174)统管按钮 / 链接 / 焦点环 / 激活态,克制且专业
- **衬线标题**(weight 500、负字距、紧行高)= 政务信任感的来源,不可替换成通用 sans
- 分层阴影(card → hover → pop → modal)建立 elevation 层次 = 高级感核心
- agent 回答走**全宽阅读排版**而非气泡,仅用户消息用气泡 —— 强调"读报告"而非"聊天"
- 每条政策 / 机会带**来源引用 chip**,呼应 RAG 与档案逐字段来源的产品价值
- 原生明暗双主题(next-themes),暗色为暖墨黑 + 青绿高光

## 配色

配色的**唯一真源是 `ui/src/app/globals.css`**。本文件的 `colors:` 只是它的镜像,方便 AI agent 阅读。改色先改 globals.css 的 CSS 变量,再同步这里——不要在组件里硬编码 hex。

- **品牌青绿** `{colors.primary}`:按钮、链接、焦点环、激活侧栏、进度。是产品唯一的"信号色",不要滥用到大面积背景。
- **暖中性系**:画布 `{colors.canvas}` → 卡片面 `{colors.surface}` → 次级面 `{colors.surface-soft}`,三级建立层次;分隔线统一 `{colors.hairline}`。
- **强调面** `{colors.accent-surface}`(极淡品牌色):hover 态、来源 chip、高匹配强调卡——让品牌色渗透到细节而不喧宾夺主。
- **语义色**克制:青绿复用为"有效/进行中",暖琥珀 `{colors.warning}` 表"临近截止",红 `{colors.error}` 仅校验错误 / 已过期。避免大红大绿的信号灯感。
- **图表色阶**围绕主色铺开(chart-1..5),暖调和谐,不要引入冷蓝紫。

## 排版

### 字体栈
- **标题(衬线)**:`--font-serif` = `Source Han Serif SC, Noto Serif SC, Songti SC, STSong, SimSun, ui-serif, Georgia, serif`。优先系统已装中文衬线,**零网络加载**。用于页面主标题、区块 display 标题、政策原文标题。
- **正文(无衬线)**:系统 sans 栈,承载正文、卡片标题、按钮、表格。
- **等宽 mono**:政策编号、金额、截止日期、来源引用、工具调用 / 代码块。

### 层级要点
| Token | 字号/字重 | 用途 |
|---|---|---|
| `{typography.display-xl}` | 48 / 500 衬线 | 页面主标题 |
| `{typography.display-lg}` | 36 / 500 衬线 | 区块标题、政策标题 |
| `{typography.display-md}` | 28 / 500 衬线 | 卡片主标题、详情副标 |
| `{typography.title-lg/md/sm}` | 22–16 / 600 sans | 卡片标题、区块小标 |
| `{typography.body-lg}` | 17 / 400,行高 1.7 | **政策原文阅读** |
| `{typography.body-md}` | 15 / 400,行高 1.6 | 正文、聊天气泡 |
| `{typography.body-sm}` | 13 / 400 | 次级说明、表格 |
| `{typography.mono}` | 13 等宽 | 编号 / 金额 / 来源 / 工具调用 |

### 原则
- 标题衬线用 **weight 500 + 负字距 + 紧行高(1.15–1.25)**,克制优雅,避免"标语感"。
- 政策长文用 `body-lg` **行高 1.7**、行宽上限 **720px** 护眼(见 `policy-doc-surface`)。
- 中文**不做 uppercase**;`micro-uppercase` 仅用于英文编号 / eyebrow。

## 布局

- **基础栅格**:8px 增量的间距系统(`{spacing.*}`)。
- **应用主框架**:左侧栏(`sidebar-region`,暖灰 + 品牌色激活)+ 右侧主内容区。侧栏承载知识库 / 政策 / 资质 / 赛事 / feed / 会话 / 企业档案 / agent-memory 等模块导航。
- **聊天单窗口**:agentic RAG 主交互——消息流居中(阅读行宽),底部悬浮 `chat-composer`。工具调用用 `tool-use-block` 折叠展示过程。
- **政策 / 机会详情**:`policy-doc-surface` 阅读容器,大内边距 + 行宽上限。
- **数据密集列表**:feed / 资质 / 赛事用 `card-interactive` 卡片流或 `data-table`,信息密度优先、间距精确。
- **留白哲学**:阅读面慷慨留白;数据面紧凑克制。两种密度并存,靠画布/间距区分而非新色。

## 层次与深度

分层阴影是高级感的核心,严格分四级(对应 `{shadows.*}` 与 globals.css 的 `--shadow-*`):

| 级别 | 阴影 | 用途 |
|---|---|---|
| card | `0 2px 8px rgba(28,33,39,0.05)` | 静置卡片、stat tile |
| hover | `0 8px 24px rgba(28,33,39,0.07)` | 卡片 hover 抬升 |
| pop | `0 16px 40px rgba(28,33,39,0.10)` | 下拉、popover、toast |
| modal | `0 24px 60px rgba(28,33,39,0.14)` | 模态、对话框 |

- 静置卡片用**极淡阴影 + 1px hairline** 双重界定,不要重阴影。
- 只有交互抬升(hover / 浮层)才升级阴影级别,建立空间纵深。

## 形状

| Token | 值 | 用途 |
|---|---|---|
| `{rounded.xs}` 4px | tag chip |
| `{rounded.sm}` 6px | 小徽章、内联输入 |
| `{rounded.md}` 8px | **按钮、输入框**(sober 几何) |
| `{rounded.lg}` 12px | **卡片**(= --radius) |
| `{rounded.xl}` 16px | 大面板、模态、chat-composer |
| `{rounded.full}` | 仅 pill tab / 状态徽章 / 头像 |

按钮用 8px 直角圆角,**不用全圆角 pill**——政务产品要 sober,不要消费级的圆润感。

## 组件

- **按钮**:主操作 `button-primary`(青绿);次级 `button-secondary`(描边);低强度 `button-ghost`(品牌色 hover 面);危险 `button-destructive`。图标操作 `icon-button`。
- **卡片**:内容 `card-base`;可点击列表项 `card-interactive`(hover 升阴影 + 品牌色描边);强调 `card-accent`(高匹配政策 / 临近截止机会);阅读 `policy-doc-surface`。
- **聊天**:用户消息 `chat-bubble-user`(青绿气泡),agent 回答 `chat-bubble-agent`(**全宽阅读排版,非气泡**);过程 `tool-use-block`;来源 `citation-chip`。
- **状态徽章**:`badge-status-active`(在报名期/有效)、`badge-status-warning`(临近截止)、`badge-status-expired`(已过期)。标签用 `tag-chip`。
- **导航**:`sidebar-region` + `sidebar-nav-item(-active)`(品牌色激活);顶部切换用 `pill-tab(-active)`。
- **数据**:`data-table` + `data-table-row`;概览 `stat-tile`。
- **浮层**:`modal` / `popover` / `toast`(sonner),各自对应阴影级别。

## Do's and Don'ts

### Do
- 标题**一律用衬线** `--font-serif`,这是政务信任感的核心识别。
- 品牌青绿 `{colors.primary}` 作为**唯一信号色**,统管按钮 / 链接 / 焦点 / 激活。
- 用极淡阴影 + 1px hairline 双重界定卡片;交互才升阴影。
- agent 回答走**全宽阅读排版 + 来源 chip**,强化"读政策报告"的产品定位。
- 语义色克制;临近截止用暖琥珀,不要红色报警。
- 明暗双主题都要覆盖;暗色用暖墨黑 + 青绿提亮(brand-400)。

### Don't
- 不要把标题衬线换成通用 sans——会丢掉政务权威气质。
- 不要用全圆角 pill 按钮;政务产品要 sober 直角圆角。
- 不要把品牌青绿铺成大面积背景(仅按钮 / 强调 / 激活)。
- 不要在组件里硬编码 hex;一律引 CSS 变量(globals.css 是真源)。
- 不要引入冷蓝紫破坏暖调;图表也围绕主色铺开。
- 不要给静置卡片压重阴影。

## 响应式

| 断点 | 宽度 | 关键变化 |
|---|---|---|
| Mobile | < 640px | 侧栏收起为抽屉;卡片 1 列;聊天全宽;display 标题降一档 |
| Tablet | 640–1024px | 侧栏可折叠;卡片 2 列;表格横向滚动 |
| Desktop | ≥ 1024px | 固定侧栏 + 主内容区;卡片 2–3 列;完整 display 标题 |

- 触控目标 ≥ 40px;输入框 / 按钮有效高度 40–44px。
- 政策阅读面在任何断点保持 ≤720px 行宽。
- 数据表在窄屏用 `overflow-x:auto` 横向滚动,不换行挤压。

## 与本仓库的对接

- **真源**:`ui/src/app/globals.css`(CSS 变量 + `@theme`)。本文件是它的设计语言镜像 + 组件规范。
- **技术栈**:Next.js 16 / React 19 / Tailwind v4 / Radix(shadcn 风格)/ lucide-react / next-themes / sonner。
- **用法**:让 AI agent「参照根目录 DESIGN.md,重做/新建 X 页面/组件」;agent 直接引用组件名与 token,不发明新色值。
- 新增组件变体时,先在 `components:` 加条目,再实现;保持与 globals.css token 一致。
