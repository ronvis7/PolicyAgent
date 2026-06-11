'use client'

import Link from 'next/link'
import {SidebarTrigger, useSidebar} from '@/components/ui/sidebar'
import {ManusSettings} from '@/components/manus-settings'
import {useAuth} from '@/providers/auth-provider'

export function ChatHeader() {
  const {open, isMobile} = useSidebar()
  const {user} = useAuth()

  return (
    <header className="flex justify-between items-center w-full py-2 px-4 z-50">
      {/* 左侧操作&logo */}
      <div className="flex items-center gap-2">
        {/* 面板操作按钮: 关闭面板&移动端下会显示 */}
        {(!open || isMobile) && <SidebarTrigger className="cursor-pointer"/>}
        {/* Logo占位符 */}
        <Link href="/" className="block bg-white w-[80px] h-9 rounded-md"/>
      </div>
      {/* 右侧设置模态窗 */}
      {user?.is_platform_admin && <ManusSettings/>}
    </header>
  )
}
