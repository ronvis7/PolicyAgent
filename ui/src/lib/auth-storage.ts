import type { AuthData, AuthTenant, AuthUser, MeData } from "./api/auth";

/**
 * 认证状态持久化（localStorage）
 *
 * 令牌存于 localStorage，配合内存态 Context 使用。
 * 缓存一份登录快照用于刷新时的乐观渲染，避免白屏。
 */

const ACCESS_TOKEN_KEY = "policy_manus.access_token";
const REFRESH_TOKEN_KEY = "policy_manus.refresh_token";
const SNAPSHOT_KEY = "policy_manus.auth_snapshot";

/** 登录上下文快照（不含令牌） */
export type AuthSnapshot = {
  user: AuthUser;
  activeTenantId: string;
  role: string;
  tenants: AuthTenant[];
};

/** 登录态失效时派发的窗口事件名（刷新令牌失败 → 强制登出） */
export const AUTH_UNAUTHORIZED_EVENT = "auth:unauthorized";

const isBrowser = (): boolean => typeof window !== "undefined";

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getCachedSnapshot(): AuthSnapshot | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(SNAPSHOT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthSnapshot;
  } catch {
    return null;
  }
}

/** 写入完整认证数据（令牌 + 快照），用于登录/注册/刷新/切换组织 */
export function saveAuth(data: AuthData): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
  saveSnapshot({
    user: data.user,
    activeTenantId: data.active_tenant_id,
    role: data.role,
    tenants: data.tenants,
  });
}

/** 仅更新快照（令牌不变），用于 /auth/me 拉到最新上下文时 */
export function saveSnapshotFromMe(me: MeData): void {
  saveSnapshot({
    user: me.user,
    activeTenantId: me.active_tenant_id,
    role: me.role,
    tenants: me.tenants,
  });
}

function saveSnapshot(snapshot: AuthSnapshot): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snapshot));
}

/** 清除全部认证数据 */
export function clearAuth(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(SNAPSHOT_KEY);
}

/** 派发登录态失效事件，供 AuthProvider 监听后跳转登录页 */
export function notifyUnauthorized(): void {
  if (!isBrowser()) return;
  window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
}
