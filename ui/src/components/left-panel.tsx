'use client'

import {useCallback, useEffect, useState} from 'react'
import {usePathname} from 'next/navigation'
import {useRouter} from 'next/navigation'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import {Button} from '@/components/ui/button'
import {Badge} from '@/components/ui/badge'
import {Award, BrainCircuit, Building2, Database, KeyRound, LayoutDashboard, MessageSquareText, Plus, Radar, ScrollText, ShieldCheck} from 'lucide-react'
import {Kbd, KbdGroup} from '@/components/ui/kbd'
import {SessionList} from '@/components/session-list'
import {TenantSwitcher} from '@/components/tenant-switcher'
import {UserMenu} from '@/components/user-menu'
import {ManusSettings} from '@/components/manus-settings'
import {useAuth} from '@/providers/auth-provider'
import {feedApi} from '@/lib/api'
import {FEED_UNREAD_CHANGED_EVENT} from '@/lib/feed-events'
import {cn} from '@/lib/utils'

const primaryNav = [
  {href: '/enterprise-profile', label: '企业档案', icon: Building2},
  {href: '/briefing', label: '情报简报', icon: Radar},
  {href: '/policies', label: '公开政策库', icon: ScrollText},
  {href: '/feed', label: '工作台', icon: LayoutDashboard},
  {href: '/qualifications', label: '资质机会', icon: Award},
  {href: '/knowledge', label: '知识库', icon: Database},
  {href: '/agent-memory', label: 'Agent 记忆', icon: BrainCircuit},
  {href: '/sources', label: '数据来源', icon: ShieldCheck},
]

export function LeftPanel() {
  const router = useRouter()
  const pathname = usePathname()
  const {user, role, tenants, activeTenantId} = useAuth()
  const canOpenSettings = role === 'owner' || role === 'admin' || !!user?.is_platform_admin
  const activeTenant = tenants.find((tenant) => tenant.id === activeTenantId)

  // 工作台未读红点：挂载时拉取，并监听 Feed 页清未读/重算后的同步事件
  const [unread, setUnread] = useState(0)
  const refreshUnread = useCallback(() => {
    feedApi
      .unreadCount()
      .then((res) => setUnread(res.count))
      .catch(() => setUnread(0))
  }, [])

  useEffect(() => {
    refreshUnread()
    window.addEventListener(FEED_UNREAD_CHANGED_EVENT, refreshUnread)
    return () => window.removeEventListener(FEED_UNREAD_CHANGED_EVENT, refreshUnread)
  }, [refreshUnread])

  return (
    <Sidebar className="border-r border-[#e5e2de] bg-[#ecebea]">
      {/* 顶部的切换按钮 */}
      <SidebarHeader className="px-3 py-3">
        <div className="flex items-center justify-between">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white"/>
          <div className="flex items-center gap-1.5 rounded-full border border-[#e5e2de] bg-white px-3 py-1 text-xs font-semibold text-[#2f3747] shadow-sm">
            <span className="size-2 rounded-full bg-primary"/>
            PolicyManus
          </div>
        </div>
      </SidebarHeader>
      {/* 中间内容 */}
      <SidebarContent className="px-2 pb-2">
        {/* 新建任务 */}
        <Button
          variant="outline"
          className="mb-4 h-10 w-full cursor-pointer justify-center rounded-[10px] border-[#e5e2de] bg-white font-semibold shadow-sm hover:bg-white/80"
          onClick={() => router.push('/')}
        >
          <Plus/>
          新建任务
          <KbdGroup>
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
          </KbdGroup>
        </Button>
        <div className="mb-3 px-2 text-[11px] font-semibold tracking-wide text-[#8b92a0]">企业空间</div>
        {primaryNav.map((item) => {
          const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)
          const Icon = item.icon
          return (
            <Button
              key={item.href}
              variant="ghost"
              className={cn(
                'group relative mb-1 h-10 w-full cursor-pointer justify-start rounded-xl px-3 text-[#344054] transition-colors hover:bg-white',
                active && 'bg-white font-semibold text-[#16484a] shadow-[var(--shadow-card)]',
              )}
              onClick={() => router.push(item.href)}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-primary"/>
              )}
              <Icon className={cn('size-4', active && 'text-primary')}/>
              {item.label}
              {item.href === '/feed' && unread > 0 && (
                <Badge className="ml-auto h-5 min-w-5 justify-center px-1.5">
                  {unread > 99 ? '99+' : unread}
                </Badge>
              )}
            </Button>
          )
        })}
        <div className="mt-4 mb-2 px-2 text-[11px] font-semibold tracking-wide text-[#8b92a0]">最近咨询</div>
        {/* 会话列表 */}
        <SessionList/>
      </SidebarContent>
      {/* 底部：组织切换 + 用户菜单 */}
      <SidebarFooter className="gap-2 px-2 pb-3">
        <div className="rounded-2xl border border-[#e5e2de] bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center gap-2 text-xs text-[#8b92a0]">
            <MessageSquareText className="size-3.5"/>
            当前企业主体
          </div>
          <div className="truncate text-sm font-semibold text-[#2f3747]">
            {activeTenant?.name ?? '未选择组织'}
          </div>
          <div className="mt-1 text-xs text-[#8b92a0]">角色：{role ?? '-'}</div>
        </div>
        <SidebarMenu>
          {canOpenSettings && (
            <SidebarMenuItem>
              <ManusSettings
                defaultSetting="llm-setting"
                trigger={
                  <SidebarMenuButton className="cursor-pointer">
                    <KeyRound className="size-4"/>
                    <span>模型 API 配置</span>
                  </SidebarMenuButton>
                }
              />
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <TenantSwitcher/>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <UserMenu/>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
