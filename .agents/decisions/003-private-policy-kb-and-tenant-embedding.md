# ADR 003：私有政策库 + 双轨 Embedding

状态：已决定（2026-06-18）
关联：[[002-rag-as-agent-tool]]、[[001-use-pgvector-for-mvp]]

## 背景

两个相互纠缠的问题：

1. **Embedding 密钥是平台全局的**（`settings.embed_api_key`，`service_dependencies.py` 4 处构造
   `OpenAIEmbedding` 全用同一 key），而 LLM 已是租户级 BYO（`tenant_settings` + `get_llm_config`）。
   租户在私有库堆多少文档烧多少 embedding 配额，费用却记在平台头上，SaaS 计费说不清。
2. **公开库向量化 + 私有库混合检索**让租户问答既查私有库又查全局公开库（`knowledge.py`
   `_resolve_kb_scopes` 默认含 `list_public()`）。这逼着所有向量共享同一个 embedding 空间，
   成了反对租户级 embedding 的技术障碍。

## 决策

**Embedding 按用途拆两条轨；引入租户私有政策库；Agent 问答只在租户私有空间检索。**

### 核心洞察：矛盾在 embedding 模型，不在存储引擎

向量检索要求"查询向量与被查向量出自同一模型"才有意义。这个约束与用 pgvector / Chroma /
Milvus 无关——换库搬不走它。把 embedding 按**用途**拆两轨即可彻底解开，无需引入新数据库。

### 双轨 Embedding

| 用途 | 用谁的 key | 向量空间 | 谁买单 |
|---|---|---|---|
| 公开库向量化 + ③档案匹配查询 | **平台 key**（平台固定模型） | 公开空间 | 平台 |
| 私有库向量化 + Agent 问答查询 | **租户 key** | 各租户私有空间 | 租户 |

**两轨从不交叉检索**：③只在公开空间内查（档案 → 公开政策），Agent 问答只在租户私有空间内查。
所以同一张 pgvector 表里既有平台模型的公开切片、又有租户模型的私有切片也无妨——只要**都锁
1024 维**，各查各的、互不干扰。**一个数据库（pgvector）足够。**

平台承担"公开库向量化 + ③档案查询"成本是合理的：③是平台给所有租户的核心增值服务（从杂乱
公开库筛政策），公开政策数量有限、档案查询是短文本，量可控；租户真正烧钱的是自己堆的私有
文档，那部分租户买单。

### 四项具体决定

1. **Agent 检索范围**：`knowledge_base_search` 默认范围从"私有库 + 全局公开库"改为
   **当前租户的全部知识库**（含政策库 type + 普通 type），不再附加全局公开库（避免跨 embedding
   空间混检索）。
2. **私有政策库 = 知识库的一个 `type`**（复用现有 `KnowledgeBase`/RAG 流水线，先不另起表）。
   "从公开库收藏政策" = 把政策正文作为文档喂进该知识库并向量化（用租户 key）。后续有需求再演进。
3. **Embedding 双轨，租户轨比 LLM 更严**：平台轨保留现状（公开库 + ③查询）；新增租户轨服务
   私有库。租户 BYO 但**只换 key、模型维度锁 1024**（pgvector 列定长），保证与平台切片共列、
   与租户自己的私有切片同空间。
4. **公开库②入库与③匹配保持现状**（继续用平台 embedding 向量化与语义召回）——③语义不降级。

### 被否决的备选：引入独立向量库（Chroma / Milvus）

- 解决不了核心矛盾（embedding 模型一致性与存储引擎无关）。
- 违背 [[001-use-pgvector-for-mvp]]（明确避免 Milvus/etcd/MinIO 等重基建）。
- 增运维：多一个有状态服务，需单独管租户隔离、备份、连接、一致性。"管理更方便"是错觉——
  pgvector 与业务同库，隔离用同一套 `tenant_id`、备份用同一个 `pg_dump`（已有 cron）。

## 后果

- **③政策匹配语义召回完整保留**（与上一版"降级结构化"相比，这是双轨方案的主要收益）。
- 改动收敛：②入库、③匹配、公开库切片（`public-policy-kb` 154 切片）**均不动**。
- 新成本面：私有库那条线改用租户 key；Agent 默认范围去掉公开库；新增私有政策库（收藏）。
- `PUBLIC_KB_ID`/`PUBLIC_TENANT_ID` 与 `is_public` 机制全部保留（平台轨仍在用）。

## 改造影响面（按文件）

**基建（新增租户 embedding 轨）**
- `tenant_settings`：新增 `embed_config` JSONB 列（对称 `llm_config`，需一个 alembic 迁移）。
  租户只 BYO `api_key`，base_url/model/dimension 在解析时强制锁平台值（维度恒 1024）。
- `application/services/tenant_settings_service.py`：加 `get_embed_config(tenant_id)`
  （key 取租户、model/dimension 取平台并强制 1024）。
- `interfaces/service_dependencies.py`：`get_knowledge_service` 像 `get_agent_service` 一样解析
  当前租户、按租户取 embedding key 构造 `OpenAIEmbedding`。
  **平台轨不动**：`get_policy_ingest_service`/`get_policy_match_service` 继续用 `settings.embed_api_key`。
- 前端设置页：加 embedding key 配置项（仿 LLM key）。

**Agent 范围（去公开库）**
- `domain/services/tools/knowledge.py`：`_resolve_kb_scopes` 去掉 `list_public()` 段与指定 kb_id
  的公开库回退；更新工具 description/docstring。

**加法（私有政策库）**
- `interfaces/schemas/knowledge.py` + `knowledge_service.create_knowledge_base`：
  `CreateKnowledgeBaseRequest` 加 `type`，服务接收并落库。
- 新端点 + 流水线：从公开 `policies` 收藏政策 → 作为文档喂进指定知识库 → 走现有 ingest 向量化（租户 key）。
- 前端：`create-kb-dialog` 提交 `type`（并把误导性的"向量库后端/嵌入模型/隐私开关"对齐真实能力）；
  公开库列表/详情加"收藏到我的政策库"入口。

## 实施顺序（分阶段，各自可独立 PR）

- **阶段 A — 租户 Embedding 轨**（地基，先行）：复用 `tenant_settings` + LLM key 成熟模式，
  `get_knowledge_service` 按租户取 key（锁 1024 维）。平台轨保持不变。后续私有库向量化依赖它。
- **阶段 B — Agent 去公开库 + 私有政策库**（价值交付）：Agent 默认范围只租户私有库；知识库加
  type + "收藏政策入私有库"流水线 + UI 对齐真实能力。依赖 A。

> ②③不在改造范围（继续走平台轨），故无"做减法"阶段。
