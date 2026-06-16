# 企业档案结构化字段 + 资质能力②差距分析（A0+A1）

更新时间：2026-06-16
分支：`feat/profile-structured-fields` → **PR #22 已合并 main（2026-06-16）**

## 背景

⑥ 资质 Phase 1（PR #21）已合 main。下一块「能力② 条件差距分析」要算"差几项"，
但旧资质 matcher 纯文本子串匹配，目录 `key_conditions` 是展示串、与任何数值无关，
企业档案也没有成立日期/人员/财务/知识产权等字段。故先补档案字段（A0），再做差距分析（A1）。

引擎选型：**混合**——能结构化的硬条件确定性算，软/文本条件交人工与后续 Agent（能力③）。
字段来源：**企业手动填写**（避开 ①b 数据源难题，企业对自身数据最权威）。

## A0：企业档案结构化字段（零迁移）

- 领域模型 `EnterpriseProfile` 新增 8 字段：`established_date`(YYYY-MM-DD)、`total_staff`、
  `rd_staff`、`registered_capital_wan`、`annual_revenue_wan`、`rd_investment_wan`、
  `invention_patents`、`other_ip_count`。数值用 `Optional[...]=None` 区分"未填写"与"填了0"
  （差距分析里 **未知≠不达标**）。
- 基础设施层经 `EnterpriseProfileModel.attributes`(JSONB) 既有列承载——**零迁移**
  （`alembic head` 仍 `f7a8b9c0d1e2`），老数据缺键 `to_domain` 回落默认、向后兼容。
- 请求 schema 数值非负校验 + 成立日期宽松格式（空 / YYYY / YYYY-MM / YYYY-MM-DD）。
- 档案页新增「经营与研发指标」表单区（数值输入空串↔null 互转，owner/admin 可编辑）。

## A1：资质能力②差距分析（混合引擎结构化部分）

- 领域：`Qualification` 加 `structured_conditions: List[QualificationCondition]`
  （`metric` + `threshold` + `op(gte/lte)` + `label`）。新增 `ConditionMetric` 9 类指标
  （成立年限、总人数、研发人数、研发人员占比、研发投入占比、发明专利、知识产权总数、
  注册资本、营收），其中占比/年限为档案字段**推导**。
- 纯函数内核 `domain/services/qualification_gap.py::analyze_gap(profile, qual, today=None)`
  → `QualificationGapReport`：逐条核验 **达标/不达标/待确认(未填)**；缺字段一律"待确认"，
  **绝不误报不达标**；`manual_review` 收口无结构化对应的 `key_conditions`（label 逐字命中即去重）；
  `prerequisites_missing` 复用能力① 前置口径；`summary` 一句话总览。
- 服务 `QualificationService.analyze_gap_for_tenant(tenant_id, key)`：无档案以默认空档案分析
  （结果全"待确认"，引导先完善档案），资质不存在返回 None。
- 端点 `GET /qualifications/{key}/gap`（登录用户、限当前租户，注册在 `/{key}` 之前）。
  响应强制带 `disclaimer` + `last_reviewed`（风险纪律）。
- 目录：仅给**口径明确、数值稳定**的硬条件结构化。当前只给 `high-tech-enterprise`（高企）
  加了 成立满1年 + 科技人员占比≥10%；研发费用占比因分营收档、高新收入占比/创新评分无档案
  对应字段，留作人工/材料确认。其余 24 条待逐条**校对数值**后再补 `structured_conditions`。
- 前端：`qualification-detail.tsx` 详情视图加「条件差距分析」区块（详情弹窗打开即按档案现算），
  达标✓/不达标✗/待确认? 三态图标 + 达标计数 + 待确认引导补档案 + 前置缺口 + 待人工确认清单。
  资质机会页与 ④ Feed 详情复用同一组件，自动获得差距分析。

## 验证

- 后端单测：gap 纯函数 8 + service +3 + catalog +2 + 档案 service +2 + ORM 模型 +3 + schema +5；
  **全量 134 passed**（1 error 为既有需真库的 `test_get_status`，与本次无关）；`import app.main` OK。
- 前端 `tsc --noEmit` 干净、`eslint` 改动文件干净。
- `alembic heads` 仍 `f7a8b9c0d1e2`（A0 零迁移、A1 无表）。
- **全栈 Remote 真机走查通过**（2026-06-16，`dev-up.cmd -Mode Remote -Build` 连迁移后 .222）：
  注册→`PUT /enterprise-profile` 8 字段→`GET` 读回一致（JSONB 落 .222 验证）→
  `GET /qualifications/high-tech-enterprise/gap` 返回 成立7年≥1 **达标** / 科技人员 8%(8/100)<10% **不达标** /
  5 项 manual_review / disclaimer+last_reviewed 在位，计算正确。临时冒烟账号已事务删除清理。

## 后续

- **能力③ 材料/流程指引（A2）**：Agent 工具，复用聊天链路 + KnowledgeBaseTool 取政策原文；
  可顺带把 `manual_review` 软条件交 Agent 深化（混合引擎的"软"半边）。
- 资质目录其余条目逐条**校对数值**后补 `structured_conditions`（数值类条件交企业方核对，见风险纪律）。
- 研发费用占比的**分营收档**门槛（高企）可建模为 banded 条件，本期从简留作 manual_review。
