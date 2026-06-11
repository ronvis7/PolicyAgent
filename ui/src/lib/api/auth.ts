import { get, post } from "./fetch";

// ==================== 认证模块类型 ====================

/** 用户信息 */
export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  is_platform_admin: boolean;
};

/** 组织（租户）信息 */
export type AuthTenant = {
  id: string;
  name: string;
  slug: string;
  plan: string;
};

/** 注册/登录/刷新/切换组织成功返回的数据 */
export type AuthData = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
  active_tenant_id: string;
  role: string;
  tenants: AuthTenant[];
};

/** 当前登录上下文（/auth/me，不含令牌） */
export type MeData = {
  user: AuthUser;
  active_tenant_id: string;
  role: string;
  tenants: AuthTenant[];
};

export type RegisterParams = {
  email: string;
  password: string;
  display_name?: string;
  org_name?: string;
};

export type LoginParams = {
  email: string;
  password: string;
};

// ==================== 认证模块 API ====================

export const authApi = {
  /** 注册新用户与组织（注册者成为 owner） */
  register: (params: RegisterParams): Promise<AuthData> => {
    return post<AuthData>("/auth/register", params, { skipAuthRefresh: true });
  },

  /** 登录，默认激活第一个组织 */
  login: (params: LoginParams): Promise<AuthData> => {
    return post<AuthData>("/auth/login", params, { skipAuthRefresh: true });
  },

  /** 用 refresh 令牌轮换出新的令牌对 */
  refresh: (refreshToken: string): Promise<AuthData> => {
    return post<AuthData>(
      "/auth/refresh",
      { refresh_token: refreshToken },
      { skipAuthRefresh: true }
    );
  },

  /** 登出，吊销 refresh 令牌 */
  logout: (refreshToken: string): Promise<unknown> => {
    return post("/auth/logout", { refresh_token: refreshToken }, {
      skipAuthRefresh: true,
    });
  },

  /** 切换当前激活组织（需要登录态，会重新签发令牌） */
  switchTenant: (tenantId: string): Promise<AuthData> => {
    return post<AuthData>("/auth/switch-tenant", { tenant_id: tenantId });
  },

  /** 获取当前登录上下文 */
  me: (): Promise<MeData> => {
    return get<MeData>("/auth/me");
  },
};
