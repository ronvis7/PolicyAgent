# 跨会话 Agent 记忆（长期记忆第 2 层）

Issue：—
分支：`feat/cross-session-agent-memory`（PR 待开）
负责人：—
更新时间：2026-06-20
关联决策：`.agents/decisions/004-cross-session-agent-memory.md`

## 目标 / 背景

参加 Agent 比赛，补上"真 Agent"最具辨识度的能力——**跨会话记忆**。#59 给 Agent 装了实体记忆
（注入企业档案），但 Agent 仍只有会话内消息历史这层短期上下文，**换个会话就忘掉用户上次说过的事**
（如"今年新增 3 项发明专利"、"回答简洁些"、"重点想申报专精特新"）。本特性让 Agent 记住并跨会话召回。

## 已完成（两半结构，复刻 #59 注入范式）

**召回(读)**：会话启动按 `tenant_id` 取最近 N 条记忆 → `render_memory_context` 渲染成
`<long_term_memory>` 块 → 注入 planner/react 首条 system 消息（与企业档案同链路）。
**写入(工具式)**：新增 `MemoryTool`（`memory_save`/`memory_list`），Agent 判断"用户陈述了值得
长期记住的事实/偏好"时主动调 `memory_save` 落库；系统提示词 `<memory>` 段引导何时记/勿记噪音。

### 改动清单
- 决策：`.agents/decisions/004-cross-session-agent-memory.md`（ADR-004）。
- 领域：`models/agent_memory.py`（AgentMemory）、`repositories/agent_memory_repository.py`（协议）、
  `services/memory_context.py`（`render_memory_context` 纯函数）、`services/tools/memory.py`（MemoryTool，
  规范化精确去重、超长截断、租户懒加载隔离）。
- 基础设施：`models/agent_memory.py`（ORM，id 主键 + tenant_id 索引 + FK CASCADE）、
  `repositories/db_agent_memory_repository.py`、迁移 `c0d1e2f3a4b5`（**现 head**，接 `b9c0d1e2f3a4`，纯新增表）、
  `db_uow.py` + `repositories/uow.py` 协议 + 测试 `_fakes.py` 注册 `agent_memory`。
- 接线：`agents/base.py` 系统上下文拼接从"仅企业档案"泛化为"企业档案 + 长期记忆"两段
  （`set_memory_context()`）；`flows/planner_react.py` 会话启动多读一次记忆并注入两个 Agent、
  工具列表挂 `MemoryTool`、常量 `MEMORY_RECALL_LIMIT=30`；`prompts/system.py` 加 `<memory>` 段。
- 应用/接口：`application/services/agent_memory_service.py`（list/delete）、
  `interfaces/schemas/agent_memory.py`、`endpoints/agent_memory_routes.py`
  （`GET /agent-memories`、`DELETE /agent-memories/{id}`，限当前租户）、`service_dependencies` +
  `routes.py` 注册。
- 前端：`app/agent-memory/page.tsx`（「Agent 记忆」页：列表/记于日期/二次确认删除/空态引导）+
  `lib/api/agent-memory.ts` + index 导出 + `left-panel.tsx` 左栏入口（BrainCircuit 图标）。

## 接口与迁移

新增表 `agent_memories`（迁移 `c0d1e2f3a4b5`，**现 head**，纯新增、向后兼容）。
新增端点 `GET /agent-memories`、`DELETE /agent-memories/{memory_id}`。零新增依赖。

## 验证

- 新增单测 13：`test_memory_context.py`(3) + `test_memory_tool.py`(7) + `test_agent_memory_service.py`(3)。
- 全量离线 **274 passed, 5 skipped**（`test_status_routes` 需真库、按惯例 deselect）；`import app.main` 干净。
- 前端 `tsc --noEmit` / `eslint`（改动文件）/ `next build` 全绿，`/agent-memory` 路由已生成。

## 关键机制备注（与 #59 一致的边界）

- 系统提示词只在**会话首条消息**落库一次，故记忆注入**只对新会话生效**，存量旧会话不回溯
  （新建会话即可用上新记忆）。
- 记忆为**租户共享**：同企业多成员共用一份长期记忆（符合"企业为主体"，但偏个人化的偏好会共享）。
- 召回不用向量、按时间倒序取最近 30 条；条目无界增长靠管理页人工清理 + 注入侧 N 上限兜底。

## 未完成 / 下一步

- **真机走查待做**：迁移落库（连 .222 需随 api 启动 `alembic upgrade` 或手动）；
  真机验证"会话 A 告诉助手一件事 → 新建会话 B 助手能想起 / 记忆页可见可删"。
- 候选增强（见 ADR-004）：会话结束自动抽取事实补 `memory_save`；条目语义召回；
  记忆冲突/更新（覆盖而非追加）；memory_save 的 SSE 专属卡片（当前走通用工具事件渲染）。
- 比赛剩余两个候选功能（用户已选本次只做记忆）：**主动情报 Agent**、**自主申报助手**，后续推进。
