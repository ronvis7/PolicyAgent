import { get, post } from "./fetch";

// ==================== 公开政策库类型 ====================

/** 政策列表项（不含正文） */
export type PolicyListItem = {
  id: string;
  source: string;
  source_url: string;
  index_number: string;
  title: string;
  issuer: string;
  doc_number: string;
  status: string;
  publish_date: string | null;
  region: string;
};

/** 政策详情（含正文） */
export type PolicyDetail = PolicyListItem & {
  body_text: string;
  crawled_at: string | null;
};

/** 政策分页列表响应 */
export type PolicyListResponse = {
  items: PolicyListItem[];
  total: number;
  page: number;
  page_size: number;
};

/** 列表查询参数 */
export type ListPoliciesParams = {
  page?: number;
  page_size?: number;
  region?: string;
  issuer?: string;
  keyword?: string;
};

/** 单条政策匹配候选（③匹配输出） */
export type PolicyMatchItem = {
  policy: PolicyListItem;
  score: number; // RRF 融合总分
  structured_score: number; // 结构化命中归一化分 [0,1]
  semantic_score: number; // 语义最高相似度 [-1,1]
  matched_terms: string[]; // 命中的档案词
  reasons: string[]; // 推荐理由
};

/** 政策匹配响应（已按融合分倒序） */
export type PolicyMatchResponse = {
  items: PolicyMatchItem[];
  total: number;
};

// ==================== 公开政策库 API ====================

export const policyApi = {
  /** 分页浏览公开政策库（所有登录用户可访问） */
  list: (params: ListPoliciesParams = {}): Promise<PolicyListResponse> => {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.region) query.set("region", params.region);
    if (params.issuer) query.set("issuer", params.issuer);
    if (params.keyword) query.set("keyword", params.keyword);
    const qs = query.toString();
    return get<PolicyListResponse>(`/policies${qs ? `?${qs}` : ""}`);
  },

  /** 查看政策详情 */
  get: (policyId: string): Promise<PolicyDetail> => {
    return get<PolicyDetail>(`/policies/${policyId}`);
  },

  /** 后台触发抓取入库（仅 owner/admin，立即返回，约 1-2 分钟后数据可见） */
  ingest: (maxPages = 3): Promise<{ max_pages: number }> => {
    return post<{ max_pages: number }>(`/policies/ingest?max_pages=${maxPages}`);
  },

  /** 按当前租户企业档案匹配公开政策候选（③匹配，即时计算） */
  match: (topK = 20): Promise<PolicyMatchResponse> => {
    return get<PolicyMatchResponse>(`/policies/match?top_k=${topK}`);
  },
};
