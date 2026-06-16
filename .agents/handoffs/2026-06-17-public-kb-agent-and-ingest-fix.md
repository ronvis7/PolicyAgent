# 公开库语义检索接入 Agent + ②向量双写外键 bug 修复

更新时间：2026-06-17
分支/PR：`feat/agent-public-kb-search`（PR #28）、`fix/policy-ingest-fk-order`（PR #29），均已合并 main。

## 背景

⑥ 收口后 STATUS 最高优先级：把 Agent 知识库检索从"仅会话租户私有库"扩到也含全局公开库
（②爬取入库的公开政策库 `is_public`/系统租户 `public`），让聊天能直接基于公开政策原文带引用作答，
也增强 A2 资质指引（算完差距后取政策原文）。

## PR #28：KnowledgeBaseTool 接入公开库

- 新增仓储 `KnowledgeBaseRepository.list_public()`（按 `is_public` 过滤）——用既有标志的正路，
  避免 domain 工具跨层 import application 的系统租户常量。
- `KnowledgeBaseTool` 改为按 `(kb_id, tenant_id)` 作用域逐库检索：私有库挂会话租户、公开库挂
  各自系统租户（`public`）；`search_similar` 按 kb+tenant 过滤，故公开库须以 `public` 租户查。
- `_build_citations` 改用每个切片自带的 `tenant_id` 回查文件名（缓存键含租户），保证私有/公开
  混合检索来源归属正确。
- 范围规则：默认=私有+公开；显式 `knowledge_base_id` 先验私有再验公开；**会话硬绑定库时只检索
  该库、不附加公开库**（尊重用户主动收窄）。工具 description 同步告知覆盖公开政策库。
- 新增知识工具单测 3（默认含公开/显式公开 id/绑定排除公开）。零迁移、无前端（引用卡片本就通用渲染）。

## PR #29：②向量双写外键 bug（真机走查发现）

**现象**：.222 的 `document_chunks` 整表为空 —— ②公开政策向量双写**每次都静默失败并整笔回滚**，
导致语义检索/③匹配语义半边/Agent 公开库问答全检索不到。

**根因**：`policy_ingest_service._index_policy` 同一事务内先 `save(knowledge_file)`（ORM pending）
再 `add_many(document_chunks)`，但二者 ORM 模型间**未声明 `relationship`**，`autoflush=False` 下
commit 时 flush 顺序不定，子行 `document_chunks` 可能先于父行 `knowledge_files` 写入 →
违反 `fk_document_chunks_kf_id_knowledge_files` → 整笔回滚（被 best-effort `try/except` 吞成
warning，外部只见 `indexed=0`）。私有 RAG 上传路径无此问题（文件在独立事务先 commit）。

**修复**：`save` 父行后显式 `await uow.flush()` 再写子行——与 `auth_service` 注册时
"先 flush 父行避免 membership 外键失败" 同址同法。1 行修复（+注释）。

> 影响面提示：此 bug 不止公开库问答；**任何走该入库路径的语义索引**都受影响。私有库上传走的是
> `knowledge_service`（文件独立事务先 commit），未受影响。

## 真机走查（连 .222，2026-06-16/17）

1. 复现：原代码 `ForeignKeyViolationError ... knowledge_file_id not present in knowledge_files`，
   整笔 ROLLBACK，public chunks=0。
2. 修复后重跑 `POST /policies/ingest?source=wnd`：public chunks **0 → 154**（40 files）持久化。
3. PR #28 联动确定性验证：**零私有库的新租户**经 `KnowledgeBaseTool` 默认范围检索"无锡低空经济政策"
   → 命中 3 条，**全部来自 `public-policy-kb`**（score 0.85/0.84/0.82，内容正确，来源归属正确）。
4. 单测全量 147 passed。冒烟账号已事务删除清理；**公开政策数据（154 切片/40 文件）保留**（真实②内容）。

## 后续 / 注意

- 排障坑：app 自身 logger 未输出到 docker stdout（仅 sqlalchemy echo 可见，因 dev `echo=True`），
  best-effort `try/except` 又把 `_index_policy` 异常吞成 warning，故 bug 长期隐形。排查时直接
  在容器内复现 `_index_policy` 才暴露 FK 违例。后续可考虑把 app 日志接到 stdout（STATUS 可选项已列）。
- Windows `curl` 发 UTF-8 中文请求体会被 "error parsing the body" 截断；真机走查统一用 api 容器内
  Python（urllib）发请求规避（不影响前端浏览器）。
- 公开库语义检索现已可用，但仍只有无锡新吴区一个来源；多区域需为各门户单独做爬虫（①b 教训）。
