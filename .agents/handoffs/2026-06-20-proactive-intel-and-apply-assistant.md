# 主动情报 Agent + 自主申报助手

Issue：—
分支：`feat/cross-session-agent-memory`（与跨会话记忆同分支，PR 待开）
负责人：—
更新时间：2026-06-20

## 背景

Agent 比赛收尾，继跨会话记忆之后再补两块"真 Agent"特质：**主动性**（替你盯着、主动产出）与
**目标驱动编排**（把一句话目标办成可交付方案）。与记忆一起，凑齐"记得你 / 替你盯着 / 把事办成"三件套。
最终一起出了总演示文档 `.agents/DEMO_WALKTHROUGH.md`。

## A. 主动情报 Agent（已完成）

Agent 在企业离线时自主扫描已匹配机会（③政策/⑥资质差距/⑤临期），**LLM 归纳出带理由的优先级简报**，
主动呈现。复用 ReportService 聚合 + deadline_extractor 的 best-effort LLM 范式。

- 领域：`models/intel_briefing.py`（IntelBriefing/BriefingItem/BriefingUrgency + 免责）、
  `services/briefing_composer.py`（纯函数：`build_facts`/`build_messages`/`parse_briefing` +
  **确定性兜底** `fallback_briefing`，无 LLM/解析失败兜底，保证始终有产出）。
- 基础设施：`models/intel_briefing.py` ORM（tenant_id 主键、content JSONB，每租户最新一份）、
  `db_intel_briefing_repository.py`、迁移 `d1e2f3a4b5c6`（**现 head**，接 `c0d1e2f3a4b5`）、
  uow/db_uow/fakes 注册；并给 `enterprise_profile` 仓储加 `list_tenant_ids`（供批量重算定位活跃租户）。
- 应用：`services/briefing_service.py`（`generate` 复用 ReportService.build_brief → LLM 优先/兜底 →
  持久化；`get_latest`；`regenerate_all` 遍历已建档租户）。LLM 用平台默认（系统级生成无租户），缺 key 走兜底。
- 接口：`schemas/briefing.py` + `endpoints/briefing_routes.py`（`GET /briefings/latest`、
  `POST /briefings/generate`，限当前租户）+ deps 注册。
- 定时：`scheduler/briefing_refresh_scheduler.py`（`BriefingRefreshScheduler`，每天 04:30 调
  `regenerate_all`，错开 04:00 重爬）；`core/config.py` 加 `BRIEFING_REFRESH_*` 开关；`main.py` lifespan 起停。
- 前端：`app/briefing/page.tsx`（情报简报页：总览卡 + 情报项[紧迫度圆点/类别徽章/理由/下一步] +
  「立即生成」+ AI/规则归纳标注 + 免责）+ `lib/api/briefing.ts` + index 导出 + 左栏「情报简报」入口（Radar 图标）。

## B. 自主申报助手（已完成）

把"帮我把某资质申报准备好"这类**目标驱动**诉求一站式办成。在 `QualificationTool` 扩 `qualification_apply_plan(key)`：

- 聚合 `analyze_gap` 的逐条核验 + 需补齐缺口（不达标 + 档案未填待确认 + 缺前置 + 需人工确认）+
  主要材料 + 时间线/政策依据/价值，输出 `kind="plan"` 的 `QualificationToolData`（带 disclaimer/last_reviewed）。
- `prompts/system.py` 加 `<application_assistant>` 段：目标诉求优先调 apply_plan 一站式产出、
  待确认项引导补档案、需核对项结合 knowledge_base_search。
- 前端零改动即可呈现：`QualificationPreview` 按 title/summary/lines/disclaimer 通用渲染，`kind="plan"` 直接生效；
  仅 `tool-use/utils.ts` 加 `qualification_apply_plan` 调用中文案。

## 接口与迁移

新增表 `intel_briefings`（迁移 `d1e2f3a4b5c6`，**现 head**，纯新增）。新增端点 `GET /briefings/latest`、
`POST /briefings/generate`。新增 Agent 工具 `qualification_apply_plan`。零新增依赖。

## 验证

- 新增单测 14：briefing_composer 6 + briefing_service 5 + qualification apply_plan 3。
- 全量离线 **288 passed, 5 skipped**（含本轮 + 跨会话记忆的 13）；`import app.main` 干净；
  前端 tsc/eslint/next build 全绿，`/briefing` 路由已生成。

## 关键备注

- 简报 best-effort：无 LLM/解析失败回退确定性兜底（卡片标注"规则归纳"vs"AI 归纳"），始终有产出。
- 定时重算单实例假设（同重爬调度器）；多副本需分布式锁。
- apply_plan 的"待确认"项绝不误报不达标（沿用 gap 风险纪律），缺字段引导补档案。

## 未完成 / 下一步

- **真机走查待做**：迁移落库（`agent_memories` + `intel_briefings`）；真机验三件套：
  跨会话记忆 / 「立即生成」情报简报 / 「帮我把高企申报准备好」出方案。
- 候选增强：简报按租户个性化阈值与去重、情报项点击跳转对应详情；申报方案导出/落库为可跟踪清单。
