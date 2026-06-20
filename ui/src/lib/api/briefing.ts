import { get, post } from "./fetch";

// ==================== 主动情报简报类型 ====================

/** 情报项紧迫度 */
export type BriefingUrgency = "high" | "normal" | "low";

/** 一条情报要点 */
export type BriefingItem = {
  title: string;
  category: string;
  reason: string;
  action: string;
  urgency: BriefingUrgency;
};

/** 情报简报 */
export type Briefing = {
  has_briefing: boolean;
  headline: string;
  items: BriefingItem[];
  generated_by: string; // llm | fallback
  disclaimer: string;
  generated_at: string | null;
};

// ==================== 主动情报简报 API ====================

export const briefingApi = {
  /** 获取最新一份情报简报（从未生成则 has_briefing=false） */
  latest: (): Promise<Briefing> => {
    return get<Briefing>("/briefings/latest");
  },

  /** 立即生成一份情报简报 */
  generate: (): Promise<Briefing> => {
    return post<Briefing>("/briefings/generate");
  },
};
