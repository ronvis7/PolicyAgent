import { get, post, put } from "./fetch";

// ==================== 企业档案类型 ====================

/** 企业规模 */
export type EnterpriseScale = "unspecified" | "micro" | "small" | "medium" | "large";

/** 企业档案 */
export type EnterpriseProfile = {
  company_name: string;
  province: string;
  city: string;
  district: string;
  industry: string;
  scale: EnterpriseScale;
  main_business: string;
  qualifications: string[];
  tech_domains: string[];
  keywords: string[];
  updated_at: string;
};

/** 更新企业档案参数（不含服务端维护的时间戳） */
export type UpdateEnterpriseProfileParams = Omit<EnterpriseProfile, "updated_at">;

/** 联网增强请求参数（以企业名 + 可选地区为线索） */
export type EnrichProfileParams = {
  company_name: string;
  province?: string;
  city?: string;
  district?: string;
};

/** 联网增强建议（仅供回填审阅，未落库） */
export type EnterpriseProfileEnrichment = {
  industry: string;
  scale: EnterpriseScale;
  main_business: string;
  qualifications: string[];
  tech_domains: string[];
  keywords: string[];
  sources: string[];
  note: string;
};

// ==================== 企业档案 API ====================

export const profileApi = {
  /** 获取当前组织的企业档案（未填写过返回带默认地区的空档案） */
  get: (): Promise<EnterpriseProfile> => {
    return get<EnterpriseProfile>("/enterprise-profile");
  },

  /** 整体更新当前组织的企业档案（仅 owner/admin） */
  update: (params: UpdateEnterpriseProfileParams): Promise<EnterpriseProfile> => {
    return put<EnterpriseProfile>("/enterprise-profile", params);
  },

  /** 联网增强：以企业名联网检索 + AI 抽取建议字段（不落库，仅 owner/admin） */
  enrich: (params: EnrichProfileParams): Promise<EnterpriseProfileEnrichment> => {
    return post<EnterpriseProfileEnrichment>("/enterprise-profile/enrich", params);
  },
};
