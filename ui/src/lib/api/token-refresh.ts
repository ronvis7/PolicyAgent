import { API_BASE_URL } from "./base";
import {
  clearAuth,
  getRefreshToken,
  notifyUnauthorized,
  saveAuth,
} from "../auth-storage";
import type { AuthData } from "./auth";

/**
 * 访问令牌刷新（单飞 single-flight）
 *
 * 使用原生 fetch 直连 /auth/refresh，避免与 fetch 封装/authApi 形成循环依赖，
 * 也避免刷新请求自身被刷新拦截器再次拦截。
 *
 * 并发请求同时触发 401 时共享同一个刷新 Promise，刷新成功后各自携带新令牌重试。
 */

let refreshPromise: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = doRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function doRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    handleFailure();
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const body = (await response.json()) as {
      code: number;
      data: AuthData | null;
    };

    const ok =
      response.ok && (body.code === 0 || body.code === 200) && body.data;
    if (!ok || !body.data) {
      handleFailure();
      return null;
    }

    saveAuth(body.data);
    return body.data.access_token;
  } catch {
    handleFailure();
    return null;
  }
}

function handleFailure(): void {
  clearAuth();
  notifyUnauthorized();
}
