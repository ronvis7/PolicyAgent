'use client'

import React, {useEffect, useState} from 'react'
import {usePathname, useRouter} from 'next/navigation'
import {Info, Loader2, X} from 'lucide-react'
import {SidebarProvider} from '@/components/ui/sidebar'
import {SessionsProvider} from '@/providers/sessions-provider'
import {LeftPanel} from '@/components/left-panel'
import {useAuth} from '@/providers/auth-provider'

/** 无需登录即可访问的路由 */
const PUBLIC_ROUTES = ['/login', '/register']

function FullScreenLoader() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-background">
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
  const {status, activeTenantId, tenants} = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const [personalNoticeDismissed, setPersonalNoticeDismissed] = useState(false)

  const isPublicRoute = PUBLIC_ROUTES.includes(pathname)
  const activeTenant = tenants.find((t) => t.id === activeTenantId) ?? null
  const showPersonalNotice = activeTenant?.is_personal === true && !personalNoticeDismissed

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
        <div className="flex flex-1 flex-col bg-background h-screen overflow-hidden">
          {showPersonalNotice && (
            <div className="flex items-start gap-2 border-b border-[#f2e6c2] bg-[#fff8e8] px-4 py-2 text-sm text-[#8a6d3b]">
              <Info className="mt-0.5 size-4 shrink-0" />
              <div className="min-w-0 flex-1">
                你当前在<span className="font-medium">个人工作区「{activeTenant?.name}」</span>。
                这是提交加入申请后的临时空间——若在等待管理员批准，请耐心等待；
                若你本想为自己的公司首次建工作区，请退出后用「创建新组织」重新注册。
              </div>
              <button
                type="button"
                aria-label="关闭提示"
                className="shrink-0 cursor-pointer rounded p-0.5 hover:bg-[#f2e6c2]"
                onClick={() => setPersonalNoticeDismissed(true)}
              >
                <X className="size-4" />
              </button>
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-hidden">
            {children}
          </div>
        </div>
      </SidebarProvider>
    </SessionsProvider>
  )
}
