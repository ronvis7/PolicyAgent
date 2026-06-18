# 私有政策库 + 双轨 Embedding —— 阶段 A（租户级 Embedding BYO key）

Issue：无
分支：`feat/private-policy-kb` → **PR #42（待 CI/合并）**
关联：ADR `003-private-policy-kb-and-tenant-embedding`
更新时间：2026-06-18

## 背景 / 缘起

知识库走查中发现两个问题：① embedding 密钥全局固定（`settings.embed_api_key`），租户在私有库
堆文档烧的 embedding 配额却记平台账上，SaaS 计费说不清；② 新建知识库 UI 的"3 种向量库类型 /
嵌入模型 / 隐私开关"是纯前端摆设（后端只收 name+description，type 永远 'general'，向量库实为
pgvector 而非 Chroma/Milvus/LightRAG）。

产品负责人定方向：公开库信息杂、价值在"帮企业筛 + 自维护一份干净的"，故引入**私有政策库**
（每租户私有、向量化），公开库改为只结构化浏览/筛选。最初设想"公开库不向量化"，讨论后收敛为
**双轨 Embedding**（更优）：见 ADR 003。

## 双轨核心（ADR 003）

矛盾在"embedding 模型一致性"，不在存储引擎——换 Chroma/Milvus 解决不了，且违背 [[001-use-pgvector-for-mvp]]。
按用途拆两轨：

| 用途 | key | 空间 | 谁买单 |
|---|---|---|---|
| 公开库向量化 + ③档案匹配查询 | 平台 key | 公开空间 | 平台 |
| 私有库向量化 + Agent 问答查询 | 租户 key | 各租户私有空间 | 租户 |

两轨从不交叉检索（③只查公开、Agent 问答只查私有），pgvector 单库共存（都锁 1024 维）。
**③政策匹配语义召回完整保留**（相比早期"降级结构化"方案，这是双轨的主要收益）。

## 本阶段（A）交付 —— 租户 Embedding 轨

**后端**
- `tenant_settings` 加 `embed_config` JSONB 列（迁移 `b9c0d1e2f3a4`，对称 `llm_config`）。
- `TenantSettingsService.resolve_embed_config / update_embed_config`：租户只 BYO `api_key`，
  **base_url/model/dimension 强制锁平台**（维度恒 1024、保证向量空间一致）。
- `get_knowledge_service` 改 async、按当前租户解析 embedding key（组织自定义优先，回落平台 `.env`）；
  上传文件的后台向量化复用本次请求注入的 service，故按租户 key 计费。
- 新增 `GET/POST /app-config/embedding`（owner/admin）+ schema `PublicEmbedConfig`/`UpdateEmbedConfigRequest`。
- **平台轨（②入库 `policy_ingest_service` / ③匹配 `policy_match_service`）完全未动**。

**前端**
- 设置弹窗新增「向量模型」tab（owner/admin）：只填组织 embedding key，模型/维度只读锁定。
- 新增 `EmbedConfig` 类型 + `configApi.get/updateEmbedConfig`。

## 验证

- 后端 6 个新单测 + 全量 **188 passed**（本地 `api/.venv`；生产镜像不含 pytest）。
- 迁移本地库 upgrade ✓ + **.222 真机落库**（`alembic current = b9c0d1e2f3a4`）。
- 端点连 .222 冒烟：未配回落平台（model=text-embedding-v3, dim=1024）→ 配 key 后 is_custom=True
  且模型/维度仍锁 1024 ✓。冒烟账号已按 `email LIKE 'probe-%'` 清理，共享库无残留。
- 前端 tsc + eslint 改动文件全绿（next build 交 CI）。

## 踩坑记录

- **函数默认值就地求值**：`get_knowledge_service` 默认参数 `Depends(_get_optional_tenant_id)`
  引用了定义在后面的依赖，模块加载即 `NameError`。把函数移到依赖定义之后解决。这种坑只有**真重建
  容器**才暴露（旧镜像 import / 离线单测抓不到）——记忆 `docker-dev-rebuild`：改代码必须 `-Build`。
- `docker compose up`（不经 dev-up）会切回本地 postgres；真机验证务必 `dev-up -Mode Remote`。

## 待续（ADR 003 阶段 B）

- Agent `knowledge_base_search` 默认范围去掉全局公开库（`knowledge.py::_resolve_kb_scopes` 删 `list_public`）。
- 私有政策库 = 知识库的一个 `type`：`CreateKnowledgeBaseRequest` 加 `type`、服务接收落库；
  新增"从公开 `policies` 收藏政策 → 喂进知识库 → 走现有 ingest 向量化（租户 key）"流水线 + UI。
- `create-kb-dialog` 提交 `type`，并把误导性的"向量库后端/嵌入模型/隐私开关"对齐真实能力。
