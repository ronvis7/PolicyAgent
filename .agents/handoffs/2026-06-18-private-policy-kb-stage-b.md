# 私有政策库 + 双轨 Embedding —— 阶段 B（Agent 去公开库 + 私有政策库收藏）

Issue：无
分支：`feat/private-policy-kb-stage-b` → **PR 待开**
关联：ADR `003-private-policy-kb-and-tenant-embedding`、handoff `2026-06-18-tenant-embedding-stage-a`
更新时间：2026-06-18

## 背景

ADR 003 阶段 A（租户级 Embedding BYO key）已合并 main（PR #42）。本阶段交付价值侧：
Agent 问答只查租户私有空间、新增私有政策库（从公开库收藏政策入私有库、用租户 key 向量化）、
前端把误导性的"向量库后端/嵌入模型/隐私开关"摆设对齐真实能力。

## 本阶段（B）交付

**后端**

- **B-1 Agent 去公开库**：`domain/services/tools/knowledge.py::_resolve_kb_scopes` 删掉
  `list_public()` 段与指定 kb_id 的公开库回退。默认范围 = 当前租户全部知识库（含 policy
  type）；指定 kb_id 仅校验租户归属，未命中返回空（不再跨 embedding 空间混检索）。工具
  description/docstring 同步更新。**双轨从不交叉检索**：③仍查公开空间（平台轨未动），
  Agent 问答只查租户私有空间。
- **B-2 type 字段**：`KnowledgeBaseType` 加 `POLICY`；`CreateKnowledgeBaseRequest` 加 `type`、
  `KnowledgeService.create_knowledge_base` 接收并落库、端点透传。**零迁移**——`knowledge_bases.type`
  列早已存在（server_default `'general'`），本期只是让它从前端可设。
- **B-3 收藏政策入私有库流水线**：
  - `KnowledgeService.collect_policy(kb_id, tenant_id, owner_id, policy_id)`：校验目标库属当前租户
    且 type=policy、政策存在且正文非空；按 `uuid5(ns, "{tenant}:{kb}:{source_url}")` 派生确定性
    file id（重复收藏幂等替换）；只建占位 `KnowledgeFile`(uploaded)，向量化交后台。
  - `KnowledgeService.ingest_collected_policy(...)`：后台取政策正文→分块→**用 self.embedding
    （阶段 A 起按租户 key 注入）向量化**→落 `document_chunk`（挂当前租户）→置 indexed；失败
    置 error_indexing。chunk_metadata 带 source_url/title 便于来源回溯。
  - 端点 `POST /knowledge-bases/{kb_id}/policies`（body `{policy_id}`），后台任务排 `ingest_collected_policy`。
  - **平台轨完全未动**：②`policy_ingest_service`（公开库 `_index_policy` 仍用平台 key/PUBLIC 租户）、
    ③`policy_match_service` 不改。

**前端**

- `components/knowledge/create-kb-dialog.tsx`：类型卡 Chroma/Milvus/LightRAG → **通用文档库 /
  私有政策库**（真实 `type`，提交进 `onCreate`）；嵌入模型写死的 `siliconflow/.../bge-m3` →
  "组织 Embedding 模型 · 1024 维（统一锁定）"+ 指向「设置·向量模型」的说明；无效的隐私 Switch →
  组织隔离静态说明。
- `app/policies/page.tsx`：详情面板加「**收藏到我的政策库**」下拉（挂载时拉租户 KB、筛 type=policy；
  无 policy 库时提示去「知识库」新建）。
- `app/knowledge/page.tsx`：`getKbStyle` 改由真实 `kb.type` 驱动（policy→Landmark/私有政策库、
  general→FileText/通用文档库），卡片去掉误导的 `BAAI/bge-m3` 徽章、改显类型徽章 + "1024 维"。
- `lib/api/knowledge.ts`：加 `KnowledgeBaseType` 类型、`CreateKnowledgeBaseParams.type`、
  `createKnowledgeBase` 提交 type、`collectPolicy(kbId, policyId)`。

## 验证

- 后端新增单测：`test_knowledge_collect_policy.py` 5（类型校验/政策缺失/空正文/幂等占位/后台落库）；
  `test_knowledge_tool.py` 2 个旧测试改写为「默认不含公开库」「显式公开库 id 不再回退」。
- 全量 **193 passed**（唯一 error 为既有需真库的 `test_get_status`）；`import app.main` OK。
- 前端 tsc + eslint（改动文件）+ `next build` 三绿。

## 待续 / 遗留

- **真机走查未做**：阶段 A 踩过"函数默认参数就地求值 NameError 只有重建容器才暴露"的坑
  （记忆 `docker-dev-rebuild`）。本期虽 `import app.main` 已过，仍应 `dev-up -Mode Remote -Build`
  连 .222 实跑：建私有政策库→收藏一篇公开政策→等 indexed→Agent 问答命中该私有切片、且确认
  不再检索公开库。
- **知识库列表文件数仍是占位**（`getKbFileCount` 按 id 种子随机）——上轮 UI-refresh 的路线图占位，
  接真实文件数需后端按 KB 统计 count，不在本阶段范围。
- 收藏目前以"整篇政策正文"为一个 KnowledgeFile；批量收藏（列表多选 → 一次收藏）可后续加。
