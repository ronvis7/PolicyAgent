'use client'

import Link from 'next/link'
import {SidebarTrigger, useSidebar} from '@/components/ui/sidebar'
import {ManusSettings} from '@/components/manus-settings'
import {useAuth} from '@/providers/auth-provider'

export function ChatHeader() {
  const {open, isMobile} = useSidebar()
  const {user, role} = useAuth()
  const canOpenSettings = role === 'owner' || role === 'admin' || !!user?.is_platform_admin

  return (
    <header className="flex justify-between items-center w-full py-2 px-4 z-50">
      {/* 左侧操作&logo */}
      <div className="flex items-center gap-2">
        {/* 面板操作按钮: 关闭面板&移动端下会显示 */}
        {(!open || isMobile) && <SidebarTrigger className="cursor-pointer"/>}
        {/* 品牌字标 */}
        <Link
          href="/"
          className="block rounded-full border border-[#e5e2de] bg-white px-3 py-1 text-xs font-semibold text-[#667085] shadow-sm"
        >
          PolicyManus
        </Link>
      </div>
      {/* 右侧设置模态窗（组织 owner/admin 或平台管理员可见） */}
      {canOpenSettings && <ManusSettings/>}
    </header>
  )
}
