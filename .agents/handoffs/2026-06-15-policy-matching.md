# 政策匹配 ③（企业档案 × 公开政策，结构化 + 语义 RRF 融合）

Issue：待创建
分支：`feat/policy-matching`（从 main `bd9a73d` 切，PR 待创建；无迁移）
更新时间：2026-06-15

## 目标

主线第③步：`企业档案 → 公开政策库 → 匹配 → 工作台 Feed`。本期做 **匹配**：按当前租户企业档案，从公开政策库 `policies` 产出「可申报政策候选」（带可解释推荐理由），供前端候选页与后续 ④Feed 复用。

## 决策（2026-06-15 与用户敲定）

1. **两路结合**：结构化命中 + 语义召回，效果优于单路。
2. **即时计算、不落表**：每次按档案现算，保证随档案/政策库实时更新；物化 `policy_matches` 留到 ④Feed（主动推送）再做。
3. **本分支范围只做匹配引擎 + 前端候选页**；公开库语义检索接入聊天 Agent（KnowledgeBaseTool 纳入 `is_public` 库）刻意不做，留作后续小分支。
4. 先合 PR #12（②）→ 从 main 切本分支（已完成）。

## 实现

### 后端
- 纯函数内核 `domain/services/policy_matcher.py`（无 IO，可测）：
  - `extract_profile_terms(profile)`：keywords+tech_domains+qualifications+industry，去空白去重保序。
  - `build_profile_query(profile)`：industry+main_business+tech_domains+keywords 拼语义查询。
  - `region_matches(profile, policy)`：政策 region 是否覆盖档案区/市（逐级）。
  - `score_terms(terms, policy)`：词表在 title(权重2)+body(权重1) 的加权命中 → (归一化分∈[0,1], 命中词)；terms 由调用方抽一次复用（避免每篇候选重算）。
  - `structured_score(profile, policy)`：`score_terms` 的便捷封装。
  - `reciprocal_rank_fusion(rankings, k=60)`：RRF，两路都召回的政策天然加权。
- 域模型 `domain/models/policy_match.py`（`PolicyMatch`：policy + score + structured_score + semantic_score + matched_terms + reasons）。
- 应用服务 `application/services/policy_match_service.py`（`PolicyMatchService(uow_factory, embedding)`）：
  - `match_for_tenant(tenant_id, top_k=20)`：载档案→无信号(词表&查询全空)短路返回[]→结构化路+语义路→`_fuse`。
  - 结构化路：`uow.policy.list_candidates(500)` 逐篇 `score_terms`，保留命中、按归一化分倒序。
  - 语义路：`embed_query` → `document_chunk.search_similar(PUBLIC_KB_ID, PUBLIC_TENANT_ID, vec, 30)` → 按 `chunk_metadata.source_url` 聚合取最高相似度 → **批量** `policy.list_by_source_urls`（一次 IN，无 N+1）。
  - `_fuse`：两路有序 id → RRF → 取 top_k → 组装 PolicyMatch + 推荐理由。
  - 边界常量：`DEFAULT_TOP_K=20`、`MAX_TOP_K=50`、`_STRUCT_CANDIDATE_LIMIT=500`、`_SEM_CHUNK_TOP_K=30`。
- 仓储：协议+DB+fakes 加 `list_candidates(limit)`、`list_by_source_urls(urls)`；`FakeDocumentChunkRepository` 加 `search_similar`（内存余弦）。
- 接口：`schemas/policy.py` 加 `PolicyMatchItem`（policy 用轻量 `PolicyListItem`，正文经详情接口按需取）/`PolicyMatchResponse`；`policy_routes.py` 加 `GET /policies/match?top_k=N`（`get_current_user`，**必须注册在 `/{policy_id}` 之前**否则被路径参数吞掉）；`service_dependencies.py` 加 `get_policy_match_service`（同 ingest 注入 OpenAIEmbedding）。

### 前端
- `lib/api/policy.ts` 加 `PolicyMatchItem`/`PolicyMatchResponse` 类型 + `policyApi.match(topK)`；`lib/api/index.ts` 补导出。
- `app/matches/page.tsx`：候选列表（排名/标题/推荐理由/命中度%/语义分/点击详情弹窗复用 `/policies/{id}`），空态引导去 `/enterprise-profile` 完善档案；「重新匹配」刷新。
- `components/left-panel.tsx` 加「政策匹配」入口（Sparkles 图标）。

## 验证

- 单测全绿：匹配器纯函数 10 + 匹配服务 4；全量 **67 passed**（跳过需真库的 `test_status_routes`）。
- `import app.main` OK；`alembic heads` 单一 `e6f7a8b9c0d1`（**无新表无迁移**）；路由顺序经 `app.routes` dump 确认 `/match` 在 `/{policy_id}` 前。
- 前端 `tsc --noEmit` exit 0、`eslint`（改动文件）exit 0。
- code-review（medium）：无正确性 bug；两处效率项（语义回查 N+1、词表重复抽取）**已修**。

## 未完成 / 下一步

- **真机验证**：DB 连通 + 公开库已抓取切片后，填好企业档案（行业/关键词/技术域），调 `GET /policies/match` 与 `/matches` 页核对候选与理由；再开 PR 合 main。
- ④ 工作台 Feed：在即时匹配上做物化（`policy_matches` 表）+ 定时刷新 + 主动推送。
- 公开库语义检索接入 Agent（KnowledgeBaseTool 纳入 is_public 库）——后续小分支。

## 风险 / 注意

- 结构化命中用子串 `in` 匹配，短词（如 "AI"）可能误命中；必要时后续加分词/边界。
- 结构化候选扫描上限 500（按发文日期倒序）；政策库超 500 后较旧政策仅靠语义路覆盖。
- 语义路依赖公开库已抓取入库；未抓取则只有结构化结果（甚至为空）。
- `region_matches` 只看区/市，未用省级；当前单区域数据足够。
