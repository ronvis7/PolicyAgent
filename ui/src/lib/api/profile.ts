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
  contest_regions: string[]; // 参赛关注地区（赛事机会按此过滤；空=不限）
  // ---- 结构化资质条件字段（手动填写，供 ⑥ 差距分析；未填写为 null）----
  established_date: string; // 成立/注册日期 YYYY-MM-DD
  total_staff: number | null; // 员工总数
  rd_staff: number | null; // 研发人员数
  registered_capital_wan: number | null; // 注册资本（万元）
  annual_revenue_wan: number | null; // 上年度营收（万元）
  rd_investment_wan: number | null; // 上年度研发投入（万元）
  invention_patents: number | null; // 发明专利数
  other_ip_count: number | null; // 其他知识产权数（实用新型/软著等）
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

  /** 从自述文本智能提取候选关键词（排除已填项），供档案编辑一键补全 */
  suggestKeywords: (text: string, exclude: string[]): Promise<{ suggestions: string[] }> => {
    return post<{ suggestions: string[] }>("/enterprise-profile/keyword-suggestions", {
      text,
      exclude,
    });
  },
};
