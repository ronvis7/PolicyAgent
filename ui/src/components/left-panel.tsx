'use client'

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
import {Building2, Database, KeyRound, Plus, ScrollText} from 'lucide-react'
import {Kbd, KbdGroup} from '@/components/ui/kbd'
import {SessionList} from '@/components/session-list'
import {TenantSwitcher} from '@/components/tenant-switcher'
import {UserMenu} from '@/components/user-menu'
import {ManusSettings} from '@/components/manus-settings'
import {useAuth} from '@/providers/auth-provider'

export function LeftPanel() {
  const router = useRouter()
  const {user, role} = useAuth()
  const canOpenSettings = role === 'owner' || role === 'admin' || !!user?.is_platform_admin

  return (
    <Sidebar>
      {/* 顶部的切换按钮 */}
      <SidebarHeader>
        <SidebarTrigger className="cursor-pointer"/>
      </SidebarHeader>
      {/* 中间内容 */}
      <SidebarContent className="p-2">
        {/* 新建任务 */}
        <Button
          variant="outline"
          className="cursor-pointer mb-3"
          onClick={() => router.push('/')}
        >
          <Plus/>
          新建任务
          <KbdGroup>
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
          </KbdGroup>
        </Button>
        {/* 企业档案入口 */}
        <Button
          variant="ghost"
          className="cursor-pointer justify-start mb-1"
          onClick={() => router.push('/enterprise-profile')}
        >
          <Building2 className="size-4"/>
          企业档案
        </Button>
        {/* 公开政策库入口 */}
        <Button
          variant="ghost"
          className="cursor-pointer justify-start mb-1"
          onClick={() => router.push('/policies')}
        >
          <ScrollText className="size-4"/>
          公开政策库
        </Button>
        {/* 知识库管理入口 */}
        <Button
          variant="ghost"
          className="cursor-pointer justify-start mb-1"
          onClick={() => router.push('/knowledge')}
        >
          <Database className="size-4"/>
          知识库
        </Button>
        {/* 会话列表 */}
        <SessionList/>
      </SidebarContent>
      {/* 底部：组织切换 + 用户菜单 */}
      <SidebarFooter>
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
