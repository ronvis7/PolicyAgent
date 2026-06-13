import { get, put } from "./fetch";

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
};
