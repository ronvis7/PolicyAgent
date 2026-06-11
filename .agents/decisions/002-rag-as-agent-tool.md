# ADR 002：RAG 以「Agent 工具」形态接入，而非独立聊天窗口

状态：已决定

日期：2026-06-11

## 背景

PolicyManus 基于 goodmanus（通用 tool-calling Agent）演化为企业政策咨询 Agent。
引入 RAG（政策知识库检索 + 引用回答）时面临交互形态选择：

1. 保留现有通用聊天窗口，另起一个并列的「RAG 聊天窗口」作为新模块；
2. 把 RAG 能力直接融进现有聊天窗口。

现有 Agent 已是工具循环架构：`react` Agent + `BaseTool` 子类（search/browser/
file/shell/mcp/a2a），工具用 `@tool` 装饰声明 OpenAI schema 供 LLM 调用。
`search_web` 工具描述中已预留「补充内部知识库未涵盖的内容」的语义位。

## 决策

采用 **agentic RAG**：单一聊天窗口，RAG 检索作为 Agent 的一个工具接入；
知识库管理做成独立的「非聊天」管理模块。具体：

- **检索能力 = 新工具** `KnowledgeBaseTool`（`knowledge_base_search`），继承
  `BaseTool`，内部经 `DocumentChunkRepository.search_similar` 完成向量检索，
  返回带引用元数据（`chunk_metadata` 的页码/位置）的 `ToolResult`。注册进
  `react` Agent 的工具集，由 LLM 自主决定何时检索。
- **知识库管理 = 独立模块**（R4 页面）：建库 / 上传文件 / 查看 `FileStatus`
  索引进度。它是管理后台 UI，**不是第二个聊天框**。
- **会话级知识库 scope**：会话可选「绑定某知识库」作为检索范围，用户可控
  grounding 边界。
- **（可选）严格模式**：若未来产品需要「只从知识库作答、必带引用、不发散」的
  确定性问答，做成现有窗口内的**模式开关**，而非独立并列的 chatbot。

## 原因

- 产品定位是「政策咨询 Agent」，用户问政策应直接得到带引用的回答，不应被迫
  先选「通用模式 / RAG 模式」。
- 复用现有 session/SSE/事件流与工具循环，避免再维护一套并列聊天基建。
- Agentic RAG（agent + 检索工具）强于纯单轮 RAG：政策咨询常需跨文档比对、
  算配额、查最新口径，这些依赖通用 Agent 的工具与推理能力。
- RAG 作为工具，是现有 `BaseTool` 体系的自然延伸，扩展点清晰、改动面小。

## 后果

- R3 形态确定为：实现 `KnowledgeBaseTool` + 引用渲染 + 会话级 KB scope 选择，
  而非另建一条独立 RAG 问答链路与窗口。
- 需要在前端聊天窗口加「知识库选择器」；引用需在消息事件流中可渲染。
- 「严格知识库模式」暂不实现（YAGNI），待产品确有强约束需求再加模式开关。
- 知识库管理模块（R4）与聊天窗口解耦，可独立开发与演进。
