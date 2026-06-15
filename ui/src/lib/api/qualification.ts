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

// ==================== 资质申报机会 API ====================

export const qualificationApi = {
  /** 按当前租户企业档案匹配可申报资质（排除地区不适用项，可申报优先） */
  listMatches: (): Promise<QualificationMatchListResponse> => {
    return get<QualificationMatchListResponse>("/qualifications");
  },

  /** 查看资质详情（核心条件/材料/时间/依据/价值，含免责声明与末次核对日期） */
  getDetail: (key: string): Promise<QualificationDetail> => {
    return get<QualificationDetail>(`/qualifications/${encodeURIComponent(key)}`);
  },
};
