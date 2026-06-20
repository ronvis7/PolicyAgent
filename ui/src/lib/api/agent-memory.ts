import { del, get } from "./fetch";

// ==================== Agent 长期记忆类型（ADR 004 跨会话记忆） ====================

/** 单条 Agent 长期记忆 */
export type AgentMemoryItem = {
  id: string;
  content: string;
  source_session_id: string | null;
  created_at: string;
};

/** Agent 长期记忆列表 */
export type AgentMemoryList = {
  items: AgentMemoryItem[];
  total: number;
};

// ==================== Agent 长期记忆 API ====================

export const agentMemoryApi = {
  /** 列出当前组织的 Agent 长期记忆（按时间倒序） */
  list: (): Promise<AgentMemoryList> => {
    return get<AgentMemoryList>("/agent-memories");
  },

  /** 删除一条 Agent 长期记忆 */
  remove: (memoryId: string): Promise<unknown> => {
    return del(`/agent-memories/${memoryId}`);
  },
};
