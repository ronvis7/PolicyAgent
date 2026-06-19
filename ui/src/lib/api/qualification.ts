import { get } from "./fetch";

// ==================== 资质申报机会类型（⑥）====================

/** 资质层级 */
export type QualificationLevel = "national" | "provincial" | "municipal" | "general";

/** 层级中文标签 */
export const QUALIFICATION_LEVEL_LABEL: Record<string, string> = {
  national: "国家级",
  provincial: "省级",
  municipal: "市/区级",
  general: "通用认证",
};

/** 单条资质匹配结果（可申报/接近 + 差距雏形） */
export type QualificationMatchItem = {
  key: string;
  name: string;
  level: string;
  issuer: string;
  category: string;
  region: string;
  score: number; // 匹配总分 [0,1]
  eligible: boolean; // 可申报(true)/接近可申报(false)
  matched_signals: string[]; // 命中信号
  missing_signals: string[]; // 待补信号
  missing_prerequisites: string[]; // 缺失前置资质
  reasons: string[]; // 可读理由
};

/** 可申报资质列表响应 */
export type QualificationMatchListResponse = {
  items: QualificationMatchItem[];
  total: number;
  eligible_count: number;
};

/** 资质详情（含风险纪律字段） */
export type QualificationDetail = {
  key: string;
  name: string;
  level: string;
  issuer: string;
  category: string;
  region: string;
  key_conditions: string[];
  materials: string[];
  timing: string;
  policy_basis: string;
  benefit: string;
  last_reviewed: string;
  disclaimer: string;
};

/** 单条硬条件核验状态 */
export type ConditionStatus = "met" | "unmet" | "unknown";

/** 状态中文标签 */
export const CONDITION_STATUS_LABEL: Record<ConditionStatus, string> = {
  met: "达标",
  unmet: "不达标",
  unknown: "待确认",
};

/** 单条硬条件核验结果（能力②） */
export type ConditionCheck = {
  metric: string;
  op: string; // gte/lte
  threshold: number;
  label: string;
  actual: number | null; // 档案推导实际值（未知为 null）
  status: ConditionStatus;
  detail: string; // 人读结论
};

/** 资质条件差距分析（能力②，含风险纪律字段） */
export type QualificationGap = {
  key: string;
  name: string;
  checks: ConditionCheck[];
  manual_review: string[]; // 需人工/材料确认的概要条件
  prerequisites_missing: string[]; // 缺失前置资质
  met_count: number;
  unmet_count: number;
  unknown_count: number;
  summary: string;
  last_reviewed: string;
  disclaimer: string;
};

/** 资质目录来源条目（全量、非租户过滤，供「数据来源」页溯源） */
export type QualificationSourceItem = {
  key: string;
  name: string;
  level: string;
  issuer: string; // 发证/认定机关
  region: string;
  policy_basis: string; // 政策依据（办法/文号）
  last_reviewed: string;
  disclaimer: string;
};

/** 全量资质目录来源响应 */
export type QualificationCatalogResponse = {
  items: QualificationSourceItem[];
  total: number;
};

// ==================== 资质申报机会 API ====================

export const qualificationApi = {
  /** 按当前租户企业档案匹配可申报资质（排除地区不适用项，可申报优先） */
  listMatches: (): Promise<QualificationMatchListResponse> => {
    return get<QualificationMatchListResponse>("/qualifications");
  },

  /** 全量资质目录来源（数据来源页用，不依赖租户档案、不做匹配过滤） */
  listCatalog: (): Promise<QualificationCatalogResponse> => {
    return get<QualificationCatalogResponse>("/qualifications/catalog");
  },

  /** 查看资质详情（核心条件/材料/时间/依据/价值，含免责声明与末次核对日期） */
  getDetail: (key: string): Promise<QualificationDetail> => {
    return get<QualificationDetail>(`/qualifications/${encodeURIComponent(key)}`);
  },

  /** 条件差距分析（能力②）：按当前租户档案逐条核验硬条件 + 待确认/待补 */
  getGap: (key: string): Promise<QualificationGap> => {
    return get<QualificationGap>(`/qualifications/${encodeURIComponent(key)}/gap`);
  },
};
