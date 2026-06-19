# Agent 实体记忆——注入企业档案为持久上下文

Issue：—
分支：`feat/agent-enterprise-context`（PR #59，已合并 main）
负责人：—
更新时间：2026-06-20

## 目标 / 问题

用户在 Agent 聊天里问"我的企业能申报哪些资质"，Agent 反过来要用户输入企业信息，
像是没读到已填好的企业档案。本质是 **Agent 没有"实体记忆"**：它不知道自己服务于哪家企业。

## 根因（三个 Explore 智能体定位，均带 file:line 证据）

数据链路其实是通的——`enterprise_profiles` 表每租户一行，`QualificationTool` 会按
`session_id→tenant_id→get_by_tenant` 懒加载档案。但：

1. **企业档案这份"实体长期记忆"从未注入 Agent 上下文**：`prompts/system.py` 通篇与企业无关；
   `agents/base.py` 发给 LLM 的只有 `system_prompt + 会话消息历史`，Agent 根本不知道服务于谁。
2. `qualification_list` 工具描述没说"自动读本企业档案、无需用户提供信息"。
3. 档案为空时返回"请先完善企业档案"，LLM 直接复述并反问用户。

> 现状记忆机制：Agent 的"记忆"= `sessions.memories`(JSONB, planner/react 各一份) 的**会话消息历史**，
> 即短期上下文窗口。**无任何跨会话/全局持久记忆**；企业档案这层语义记忆躺在库里没进过它的"脑子"。

## 已完成（第 1 层：注入企业档案为持久上下文）

- **新增** `app/domain/services/enterprise_context.py::render_enterprise_context`（纯函数）：
  把租户档案渲染成 `<enterprise_profile>` 系统提示词上下文块（企业名/地区/行业/规模/主营/已有资质/
  技术域/关键词/经营研发指标，指标仅渲染已填项区分未填≠0）；档案为空时返回"引导去档案页一键填写"块。
- `app/domain/services/agents/base.py`：`BaseAgent` 加 `_enterprise_context` + `set_enterprise_context()`，
  在记忆为空时把它拼到首条 `system` 消息（`_add_to_memory`）。
- `app/domain/services/flows/planner_react.py`：`invoke` 会话启动(已 `get_by_id` 到 session)后，
  按 `session.tenant_id` 读档案 → 渲染 → 注入 planner / react 两个 Agent。
- `app/domain/services/tools/qualification.py`：`qualification_list` 描述显式声明
  "自动读本企业档案、无需用户提供、勿反问"；空档案文案改为引导去档案页（工具内空档案判断仍是
  `profile is None`，有档案行就跑匹配、匹配不到走"未匹配"分支——不因缺企业名误伤）。
- `app/domain/services/prompts/system.py`：加 `<enterprise_awareness>` 兜底段。

效果：Agent 每轮都知道"我服务于企业X、其档案是……"；问资质→直接调 `qualification_list` 分析，
不再反问；档案空→引导去档案页一键填。**用户真机测试已确认不再反问。**

## 关键机制备注（后续改 Agent 上下文注意）

- 系统提示词只在**会话首条消息（记忆为空）时**落库一次。故企业档案注入**只对新会话生效**，
  存量旧会话不回溯。改档案后想让 Agent 用上新档案，需**新建会话**。
- 注入对 planner 和 react 两个 Agent 都做（各自独立记忆）。

## 接口与迁移

无。纯后端，**零迁移**（`enterprise_profiles` 表已存在）、零新增依赖。

## 验证

- 新增 `tests/app/domain/services/test_enterprise_context.py` 4 单测（空档案引导 / 仅缺名视为空 /
  已填渲染关键字段 / 未填指标不渲染）。
- `import app.main` 干净；全量离线 **261 passed**（`test_status_routes` 需真库、按惯例 deselect）；
  CI 三项（backend/frontend/integration）全绿后合并。
- **真机走查通过**（用户用已填档案账号新建会话问"我能申报哪些资质"，Agent 直接基于档案作答、不反问）。

## 未完成 / 下一步

- **第 2 层：跨会话通用记忆模块**（Agent 记住用户历次对话里说过的事实/偏好、跨会话召回）——
  本轮按用户决定**暂不做**，属 ADR 级架构决策的独立特性，待推进时单独出方案。
- 候选增强：档案更新后对**进行中会话**的注入刷新策略；把企业上下文也注入 en/ 英文系统提示词。
