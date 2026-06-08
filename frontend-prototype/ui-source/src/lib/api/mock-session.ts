import type {
  ChatParams,
  SSEEventData,
  SSEEventHandler,
  Session,
  SessionDetail,
  SessionFile,
  SessionsData,
} from "./types";

const STORAGE_KEY = "policy_manus_mock_sessions";

type StoredSession = SessionDetail;

function nowIso(): string {
  return new Date().toISOString();
}

function createId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function seedSessions(): StoredSession[] {
  return [
    {
      session_id: "mock_policy_report",
      title: "深圳人工智能企业政策机会分析",
      latest_message: "生成一份面向管理层的政策机会分析报告",
      latest_message_at: nowIso(),
      status: "completed",
      unread_message_count: 0,
      events: [
        {
          type: "message",
          data: {
            role: "user",
            message: "帮我分析深圳人工智能企业近期可申报的政策机会，并生成咨询报告大纲。",
          },
        },
        {
          type: "title",
          data: { title: "深圳人工智能企业政策机会分析" },
        },
        {
          type: "plan",
          data: {
            steps: [
              { id: "s1", description: "检索深圳市人工智能相关政策与申报通知", status: "completed" },
              { id: "s2", description: "提取支持方向、申报条件、主管部门和时间窗口", status: "completed" },
              { id: "s3", description: "按照咨询报告模板生成管理层摘要与行动建议", status: "completed" },
            ],
          },
        },
        {
          type: "message",
          data: {
            role: "assistant",
            message:
              "已完成政策机会分析原型。建议报告结构包括：政策环境概览、重点政策清单、企业匹配度、申报优先级、风险提示、下一步行动计划。",
          },
        },
        { type: "done", data: {} },
      ],
    },
    {
      session_id: "mock_knowledge_base",
      title: "政策知识库入库演示",
      latest_message: "抓取政策网页并下载附件入库",
      latest_message_at: nowIso(),
      status: "completed",
      unread_message_count: 0,
      events: [
        {
          type: "message",
          data: {
            role: "assistant",
            message:
              "这是一个离线演示任务：后续可以把政策网页、附件、优秀报告模板统一进入知识库，再由 Agent 检索引用。",
          },
        },
      ],
    },
  ];
}

function readSessions(): StoredSession[] {
  if (typeof window === "undefined") return seedSessions();

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const seeded = seedSessions();
    writeSessions(seeded);
    return seeded;
  }

  try {
    return JSON.parse(raw) as StoredSession[];
  } catch {
    const seeded = seedSessions();
    writeSessions(seeded);
    return seeded;
  }
}

function writeSessions(sessions: StoredSession[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

function publicSession(session: StoredSession): Session {
  const { events: _events, ...rest } = session;
  return rest;
}

function saveSession(session: StoredSession): void {
  const sessions = readSessions();
  const index = sessions.findIndex((item) => item.session_id === session.session_id);
  if (index >= 0) {
    sessions[index] = session;
  } else {
    sessions.unshift(session);
  }
  writeSessions(sessions);
}

function emitSequence(
  events: SSEEventData[],
  onEvent: SSEEventHandler,
  onDone?: () => void,
): () => void {
  const timers = events.map((event, index) =>
    window.setTimeout(() => {
      onEvent(event);
      if (index === events.length - 1) onDone?.();
    }, 350 + index * 450),
  );

  return () => timers.forEach((timer) => window.clearTimeout(timer));
}

function buildChatEvents(message: string): SSEEventData[] {
  const reportTitle = message.length > 18 ? message.slice(0, 18) : "咨询报告生成演示";

  return [
    {
      type: "message",
      data: { role: "user", message },
    },
    {
      type: "title",
      data: { title: reportTitle },
    },
    {
      type: "plan",
      data: {
        steps: [
          { id: "mock-step-1", description: "从政策知识库检索相关政策、附件和优秀案例", status: "pending" },
          { id: "mock-step-2", description: "提取报告所需的依据、口径、风险点和建议", status: "pending" },
          { id: "mock-step-3", description: "按照咨询报告模板生成初稿", status: "pending" },
        ],
      },
    },
    {
      type: "step",
      data: { id: "mock-step-1", description: "从政策知识库检索相关政策、附件和优秀案例", status: "running" },
    },
    {
      type: "tool",
      data: {
        name: "knowledge",
        function: "knowledge_search",
        args: { query: message, scope: "政策知识库" },
        status: "called",
        content: "命中 6 条政策、2 个附件、3 篇优秀报告案例",
      },
    },
    {
      type: "step",
      data: { id: "mock-step-1", description: "从政策知识库检索相关政策、附件和优秀案例", status: "completed" },
    },
    {
      type: "step",
      data: { id: "mock-step-2", description: "提取报告所需的依据、口径、风险点和建议", status: "completed" },
    },
    {
      type: "step",
      data: { id: "mock-step-3", description: "按照咨询报告模板生成初稿", status: "completed" },
    },
    {
      type: "message",
      data: {
        role: "assistant",
        message:
          "这是前端离线 mock 生成的报告初稿摘要：\n\n1. 政策环境：围绕人工智能、数字经济、专精特新和科技成果转化形成支持组合。\n2. 机会判断：优先关注研发补贴、算力券、场景开放、人才项目和产业基金。\n3. 行动建议：建立政策台账，按申报窗口拆分材料清单，并用优秀案例模板沉淀标准化报告格式。\n\n后续接入 RAG 后，这里会替换为真实知识库检索和报告生成结果。",
      },
    },
    { type: "done", data: {} },
  ];
}

export const mockSessionApi = {
  getSessions: async (): Promise<SessionsData> => ({
    sessions: readSessions().map(publicSession),
  }),

  createSession: async (): Promise<Session> => {
    const session: StoredSession = {
      session_id: createId("mock_session"),
      title: "新建咨询任务",
      latest_message: "",
      latest_message_at: nowIso(),
      status: "pending",
      unread_message_count: 0,
      events: [],
    };
    saveSession(session);
    return publicSession(session);
  },

  streamSessions: (onSessions: (sessions: Session[]) => void): (() => void) => {
    const push = () => onSessions(readSessions().map(publicSession));
    push();
    const timer = window.setInterval(push, 3000);
    return () => window.clearInterval(timer);
  },

  getSession: async (sessionId: string): Promise<Session> => {
    const session = readSessions().find((item) => item.session_id === sessionId);
    if (!session) throw new Error("Mock session not found");
    return publicSession(session);
  },

  getSessionDetail: async (sessionId: string): Promise<SessionDetail> => {
    const session = readSessions().find((item) => item.session_id === sessionId);
    if (!session) throw new Error("Mock session not found");
    return session;
  },

  chat: (
    sessionId: string,
    params: ChatParams,
    onEvent: SSEEventHandler,
    onError?: (error: Error) => void,
  ): (() => void) => {
    const message = params.message?.trim();
    if (!message) return () => undefined;

    const session = readSessions().find((item) => item.session_id === sessionId);
    if (!session) {
      onError?.(new Error("Mock session not found"));
      return () => undefined;
    }

    const events = buildChatEvents(message);
    session.status = "running";
    session.latest_message = message;
    session.latest_message_at = nowIso();
    saveSession(session);

    return emitSequence(events, onEvent, () => {
      const latest = readSessions().find((item) => item.session_id === sessionId);
      if (!latest) return;
      latest.events = [...(latest.events || []), ...events];
      latest.status = "completed";
      const titleEvent = events.find((event) => event.type === "title") as
        | { type: "title"; data: { title: string } }
        | undefined;
      if (titleEvent) latest.title = titleEvent.data.title;
      saveSession(latest);
    });
  },

  stopSession: async (): Promise<void> => undefined,

  deleteSession: async (sessionId: string): Promise<void> => {
    writeSessions(readSessions().filter((item) => item.session_id !== sessionId));
  },

  clearUnreadMessageCount: async (): Promise<void> => undefined,

  getSessionFiles: async (): Promise<SessionFile[]> => [],

  viewFile: async (): Promise<{ content: string }> => ({
    content: "Mock mode has no real sandbox files.",
  }),

  viewShell: async (): Promise<{ output: string }> => ({
    output: "Mock mode has no real shell output.",
  }),
};
