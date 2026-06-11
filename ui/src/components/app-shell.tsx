'use client'

import React, {useEffect} from 'react'
import {usePathname, useRouter} from 'next/navigation'
import {Loader2} from 'lucide-react'
import {SidebarProvider} from '@/components/ui/sidebar'
import {SessionsProvider} from '@/providers/sessions-provider'
import {LeftPanel} from '@/components/left-panel'
import {useAuth} from '@/providers/auth-provider'

/** 无需登录即可访问的路由 */
const PUBLIC_ROUTES = ['/login', '/register']

function FullScreenLoader() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-[#f8f8f7]">
      <Loader2 className="size-6 animate-spin text-muted-foreground"/>
    </div>
  )
}

/**
 * 应用外壳 + 路由守卫
 *
 * - 未登录访问受保护路由 → 跳转 /login
 * - 已登录访问 /login、/register → 跳转首页
 * - 仅在已登录时挂载 SessionsProvider 与侧边栏，避免未登录时触发受保护接口
 * - 以 activeTenantId 作为 key 重挂载，切换组织时自动重新加载该租户数据
 */
export function AppShell({children}: { children: React.ReactNode }) {
  const {status, activeTenantId} = useAuth()
  const pathname = usePathname()
  const router = useRouter()

  const isPublicRoute = PUBLIC_ROUTES.includes(pathname)

  useEffect(() => {
    if (status === 'loading') return
    if (status === 'unauthenticated' && !isPublicRoute) {
      router.replace('/login')
    } else if (status === 'authenticated' && isPublicRoute) {
      router.replace('/')
    }
  }, [status, isPublicRoute, router])

  // 初始化登录态中
  if (status === 'loading') {
    return <FullScreenLoader/>
  }

  // 公共路由（登录/注册）：裸渲染，不带侧边栏
  if (isPublicRoute) {
    return <>{children}</>
  }

  // 受保护路由但未登录：等待跳转
  if (status !== 'authenticated') {
    return <FullScreenLoader/>
  }

  // 已登录：渲染带侧边栏的应用外壳
  return (
    <SessionsProvider key={activeTenantId ?? 'no-tenant'}>
      <SidebarProvider
        style={{
          '--sidebar-width': '300px',
          '--sidebar-width-icon': '300px',
        } as React.CSSProperties}
      >
        <LeftPanel/>
        <div className="flex-1 bg-[#f8f8f7] h-screen overflow-hidden">
          {children}
        </div>
      </SidebarProvider>
    </SessionsProvider>
  )
}
