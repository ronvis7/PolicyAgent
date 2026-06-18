# 私有政策库收尾 —— 批量收藏 + 知识库真实文件数

Issue：无
分支：`feat/private-policy-kb-polish` → **PR 待开**
关联：ADR `003`、handoff `2026-06-18-private-policy-kb-stage-b`
更新时间：2026-06-18

## 背景

阶段 B handoff 列的两个「待续/遗留」：① 收藏只能逐篇；② 知识库卡片文件数是 `getKbFileCount`
按 id 种子的随机占位。本次一并收掉。

## 交付

**后端**
- 批量收藏：`KnowledgeService.collect_policies(kb_id, tenant_id, owner_id, policy_ids)`——库类型校验
  只做一次，逐篇 best-effort（政策缺失/正文为空跳过、不阻断其余），返回 `(collected=[(占位文件,
  policy_id)], skipped=[policy_id])`；端点 `POST /knowledge-bases/{kb_id}/policies/batch`
  （`{policy_ids}`，上限 100）按 collected 逐篇排 `ingest_collected_policy` 后台向量化，
  响应 `{collected_count, skipped_count}`。
- 真实文件数：仓储 `KnowledgeFileRepository.count_by_tenant(tenant_id)`（单次 `GROUP BY
  knowledge_base_id`，免 N+1）+ `KnowledgeService.file_counts` + 端点 `GET /knowledge-bases/file-counts`
  （**注册在 `/{kb_id}` 之前**，避免被路径参数捕获）。
- 单测 +3（批量 best-effort/类型校验/file_counts），全量 **196 passed**；零迁移。

**前端**
- `lib/api/knowledge.ts`：加 `collectPolicies`、`fileCounts`、`CollectPoliciesResult`。
- `hooks/use-knowledge-bases.ts`：reload 时 `Promise.all` 并发拉列表 + 文件数（文件数取不到不阻塞），
  暴露 `fileCounts`。
- `app/knowledge/page.tsx`：删除 `getKbFileCount` 随机占位，卡片用真实 `fileCounts[kb.id] ?? 0`。
- `app/policies/page.tsx`：列表勾选工具栏在选中时出「批量收藏（N）」下拉（选私有政策库），
  调 `collectPolicies`；无 policy 库时提示去新建。复用既有 `selectedIds`/`policyKbs`/`collecting`。
- tsc/eslint/next build 三绿。

## 待续

- 真机走查（同阶段 A+B）：批量收藏一批 → 知识库卡片文件数随后台入库增长 → Agent 命中。
- 收藏目前以整篇政策为一个文档；与单篇收藏共用确定性 file id，重复收藏幂等替换。
