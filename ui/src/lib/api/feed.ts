import { get, post } from "./fetch";

// ==================== 工作台 Feed 类型（④）====================

/** Feed 条目状态机 */
export type FeedStatus = "unread" | "read" | "applied" | "ignored";

/** 用户可手动设置的状态（不含 unread） */
export type SettableFeedStatus = "read" | "applied" | "ignored";

/** 工作台 Feed 条目（计算快照 + 状态） */
export type FeedItem = {
  id: string;
  type: string; // 机会类型（policy/qualification/competition）
  policy_id: string;
  title: string;
  issuer: string;
  publish_date: string | null;
  source_url: string;
  region: string;
  score: number;
  structured_score: number;
  semantic_score: number;
  matched_terms: string[];
  reasons: string[];
  status: FeedStatus;
  created_at: string | null;
  updated_at: string | null;
};

/** Feed 分页列表响应 */
export type FeedListResponse = {
  items: FeedItem[];
  total: number;
  page: number;
  page_size: number;
};

/** 列表查询参数 */
export type ListFeedParams = {
  status?: FeedStatus | "";
  page?: number;
  page_size?: number;
};

/** 重算结果 */
export type RecomputeResult = {
  new: number;
  updated: number;
};

// ==================== 工作台 Feed API ====================

export const feedApi = {
  /** 分页浏览当前租户工作台 Feed（可按状态筛选） */
  list: (params: ListFeedParams = {}): Promise<FeedListResponse> => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return get<FeedListResponse>(`/feed${qs ? `?${qs}` : ""}`);
  },

  /** 当前租户未读条数（左栏红点） */
  unreadCount: (): Promise<{ count: number }> => {
    return get<{ count: number }>("/feed/unread-count");
  },

  /** 手动重算当前租户 Feed（兜住跨租户新政策） */
  recompute: (): Promise<RecomputeResult> => {
    return post<RecomputeResult>("/feed/recompute");
  },

  /** 全部标记已读（打开工作台清红点） */
  markRead: (): Promise<{ affected: number }> => {
    return post<{ affected: number }>("/feed/mark-read");
  },

  /** 更新单条状态（read/applied/ignored） */
  setStatus: (itemId: string, status: SettableFeedStatus): Promise<FeedItem> => {
    return post<FeedItem>(`/feed/${itemId}/status`, { status });
  },
};
