# 前端 UI 刷新：公开政策库 + 知识库文档管理/图谱预留

更新时间：2026-06-17
分支：`feat/policy-ui-refresh`

## 目标

按用户提供的 `preview.html`、研究报告和 FiscalNote 参考截图，把现有前端从基础列表页收敛为更像“企业政策分析工作台”的体验；不新增悬空接口，不引入英文文案。

## 已完成

- 左侧导航重排为企业空间信息架构：企业档案、公开政策库、工作台、资质机会、知识库；保留会话列表、租户切换、模型配置。
- `/policies` 改为中文政策检索工作台：
  - 地区、部门、关键词筛选均接现有 `policyApi.list`。
  - 抓取政策接现有 `policyApi.listSources` + `policyApi.ingest`。
  - 列表卡片参考 FiscalNote 的结果审阅形态，但改为中文政策元数据、状态、文号和批量选择。
  - 右侧“政策助手”只基于已加载详情做摘要/元数据/正文预览，不调用不存在的 AI 接口。
- `/knowledge` 二次对齐为“文档知识库”卡片首页：
  - 参考用户补充截图的卡片式文档知识库页面，包含“新建知识库”卡片、知识库卡片、文件数、描述和标签。
  - `CreateKbDialog` 改为大弹窗，展示 Chroma/Milvus/LightRAG 类型卡、嵌入模型、描述和隐私开关。
  - 类型、模型、隐私均为前端展示状态；提交仍只传现有 `name`/`description`。
- `/knowledge/[id]` 二次对齐为“文件管理 + 预览”默认详情页：
  - 左侧文件表格：名称、大小、修改时间、操作；含“新建文件夹”“上传文件”和搜索。
  - 右侧预览：文件名、Source/MD 切换、全屏/面板图标；Source 展示文件元信息，MD 展示基于现有状态生成的 Markdown 占位说明。
  - 文件夹和原文预览均不新增后端能力，点击文件夹入口给出中文提示。
- `/knowledge/[id]` 保留图谱切换视图：
  - 参考图数据库截图增加搜索框、已连接状态、`Neo4j 浏览器`、`上传文件`、说明、数量输入、刷新和底部实体/关系统计。
  - `Neo4j 浏览器` 和图数据库上传仅为预留入口，点击提示“当前版本暂未接入真实 Neo4j”。
  - 图谱节点仍来自现有知识库文件列表和切片数量。

## 接口变化

无接口变化、无迁移、无新增依赖。仍使用现有：

- `/api/policies`
- `/api/policies/sources`
- `/api/policies/ingest`
- `/api/knowledge-bases`
- `/api/knowledge-bases/{id}/files`

## 验证

- `docker compose build policy-ui`：通过（Next build 内含 TypeScript 检查）。
- 改动文件 lint：通过（使用 builder 阶段镜像运行 `npm run lint -- src/app/knowledge/page.tsx 'src/app/knowledge/[id]/page.tsx' src/components/knowledge/create-kb-dialog.tsx`）。
- `git diff --check`：通过。
- `docker compose up -d --no-deps policy-ui policy-nginx`：通过，`policy-ui` healthy，Nginx 仍为 `http://127.0.0.1:8888`。
- Playwright + 当前用户 `1280565586@qq.com` 登录后走查通过：
  - `/knowledge` 显示“文档知识库”和卡片首页。
  - `/knowledge/demo-kb-policy-materials` 默认显示文件+Source/MD 预览。
  - 详情页切到“图谱”后显示“已连接”“Neo4j 浏览器”“上传文件”预留入口。

计划中的 `npm run typecheck` 在本项目不存在；改用 `docker compose build policy-ui` 验证 TypeScript。

全量 lint 未重新跑；此前失败点在既有未改文件：

- `components/manus-settings.tsx`
- `hooks/use-session-detail.ts`
- 以及若干 React Compiler warning。

本机仍无可用 npm/npx；验证均通过 Docker 镜像完成，未向宿主 `ui/node_modules` 写入依赖。

## 风险 / 后续

- 目前“文件夹”“Source/MD 原文预览”“Neo4j”都是前端交互/预留入口，不是持久化后端能力；如后续需要真实协作文件夹、原文预览或图数据库，需要新增数据模型、API 和租户隔离规则。
- `/policies` 的右侧摘要是前端辅助阅读，不代表 Agent/RAG 已接入公开政策库；公开库接入 Agent 仍按 STATUS 里的后续任务推进。
