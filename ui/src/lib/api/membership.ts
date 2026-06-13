import { get, post } from "./fetch";

// ==================== 成员管理类型 ====================

/** 组织成员角色 */
export type MembershipRole = "owner" | "admin" | "member";

/** 组织成员条目 */
export type MemberItem = {
  membership_id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: MembershipRole;
  status: string;
  created_at: string;
};

/** 成员列表响应 */
export type ListMembersData = {
  members: MemberItem[];
};

/** 按邮箱添加成员参数 */
export type AddMemberParams = {
  email: string;
  role: MembershipRole;
};

// ==================== 成员管理 API ====================

export const membershipApi = {
  /** 获取当前组织成员列表 */
  list: (): Promise<ListMembersData> => {
    return get<ListMembersData>("/members");
  },

  /** 按邮箱添加已注册用户为成员 */
  add: (params: AddMemberParams): Promise<MemberItem> => {
    return post<MemberItem>("/members", params);
  },

  /** 变更成员角色（admin / member） */
  changeRole: (membershipId: string, role: MembershipRole): Promise<MemberItem> => {
    return post<MemberItem>(`/members/${membershipId}/role`, { role });
  },

  /** 移除成员 */
  remove: (membershipId: string): Promise<void> => {
    return post<void>(`/members/${membershipId}/delete`, {});
  },

  /** 获取待审批的加入申请 */
  listRequests: (): Promise<ListMembersData> => {
    return get<ListMembersData>("/members/requests");
  },

  /** 批准加入申请 */
  approve: (membershipId: string): Promise<MemberItem> => {
    return post<MemberItem>(`/members/${membershipId}/approve`, {});
  },

  /** 拒绝加入申请 */
  reject: (membershipId: string): Promise<void> => {
    return post<void>(`/members/${membershipId}/reject`, {});
  },
};
