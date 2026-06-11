'use client'

import React, {createContext, useCallback, useContext, useEffect, useRef, useState} from 'react'
import {authApi} from '@/lib/api'
import type {AuthTenant, AuthData, AuthUser, MeData, LoginParams, RegisterParams} from '@/lib/api'
import {
  AUTH_UNAUTHORIZED_EVENT,
  clearAuth,
  getAccessToken,
  getCachedSnapshot,
  getRefreshToken,
  saveAuth,
  saveSnapshotFromMe,
} from '@/lib/auth-storage'

/** 认证状态机 */
type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

type AuthContextValue = {
  status: AuthStatus
  user: AuthUser | null
  activeTenantId: string | null
  role: string | null
  tenants: AuthTenant[]
  login: (params: LoginParams) => Promise<void>
  register: (params: RegisterParams) => Promise<void>
  logout: () => Promise<void>
  switchTenant: (tenantId: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * 认证上下文 Provider
 *
 * - 挂载时读取本地令牌：无令牌 → 未登录；有令牌 → 用缓存快照乐观渲染，
 *   并调用 /auth/me 校验与刷新上下文。
 * - 监听 auth:unauthorized 事件（刷新令牌失败时由拦截器派发）→ 强制登出。
 */
export function AuthProvider({children}: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [activeTenantId, setActiveTenantId] = useState<string | null>(null)
  const [role, setRole] = useState<string | null>(null)
  const [tenants, setTenants] = useState<AuthTenant[]>([])

  const initializedRef = useRef(false)

  const applyAuthData = useCallback((data: AuthData) => {
    saveAuth(data)
    setUser(data.user)
    setActiveTenantId(data.active_tenant_id)
    setRole(data.role)
    setTenants(data.tenants)
    setStatus('authenticated')
  }, [])

  const applyMeData = useCallback((me: MeData) => {
    saveSnapshotFromMe(me)
    setUser(me.user)
    setActiveTenantId(me.active_tenant_id)
    setRole(me.role)
    setTenants(me.tenants)
    setStatus('authenticated')
  }, [])

  const resetToUnauthenticated = useCallback(() => {
    clearAuth()
    setUser(null)
    setActiveTenantId(null)
    setRole(null)
    setTenants([])
    setStatus('unauthenticated')
  }, [])

  // ---------- 初始化：校验本地令牌 ----------
  // localStorage 仅在客户端可用，故在挂载后异步初始化（async 函数内更新状态，
  // 避免在 effect 同步体内直接 setState 触发级联渲染）。
  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    const initialize = async () => {
      const token = getAccessToken()
      if (!token) {
        setStatus('unauthenticated')
        return
      }

      // 乐观渲染：先用缓存快照填充，避免白屏
      const cached = getCachedSnapshot()
      if (cached) {
        setUser(cached.user)
        setActiveTenantId(cached.activeTenantId)
        setRole(cached.role)
        setTenants(cached.tenants)
      }

      try {
        const me = await authApi.me()
        applyMeData(me)
      } catch {
        // /auth/me 在刷新令牌后仍失败 → 视为登录态失效
        resetToUnauthenticated()
      }
    }

    initialize()
  }, [applyMeData, resetToUnauthenticated])

  // ---------- 监听登录态失效事件 ----------
  useEffect(() => {
    const handler = () => resetToUnauthenticated()
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handler)
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handler)
  }, [resetToUnauthenticated])

  // ---------- 动作 ----------
  const login = useCallback(
    async (params: LoginParams) => {
      const data = await authApi.login(params)
      applyAuthData(data)
    },
    [applyAuthData],
  )

  const register = useCallback(
    async (params: RegisterParams) => {
      const data = await authApi.register(params)
      applyAuthData(data)
    },
    [applyAuthData],
  )

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken)
      } catch {
        // 即使后端吊销失败，也继续清理本地态
      }
    }
    resetToUnauthenticated()
  }, [resetToUnauthenticated])

  const switchTenant = useCallback(
    async (tenantId: string) => {
      const data = await authApi.switchTenant(tenantId)
      applyAuthData(data)
    },
    [applyAuthData],
  )

  return (
    <AuthContext.Provider
      value={{status, user, activeTenantId, role, tenants, login, register, logout, switchTenant}}
    >
      {children}
    </AuthContext.Provider>
  )
}

/**
 * 获取认证上下文的 Hook，必须在 <AuthProvider> 内使用
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth 必须在 AuthProvider 内使用')
  }
  return ctx
}
