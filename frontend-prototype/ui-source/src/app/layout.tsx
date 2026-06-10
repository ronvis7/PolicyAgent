import React from 'react'
import type {Metadata} from 'next'
import {SidebarProvider} from '@/components/ui/sidebar'
import {SessionsProvider} from '@/providers/sessions-provider'
import {Toaster} from '@/components/ui/sonner'
import './globals.css'
import {LeftPanel} from '@/components/left-panel'

export const metadata: Metadata = {
  title: 'PolicyManus',
  description: 'PolicyManus 是面向企业的政策咨询智能体，提供政策检索、解读、匹配与报告生成能力。',
  icons: {
    icon: '/icon.png',
  },
}

export default function RootLayout(
  {
    children,
  }: Readonly<{
    children: React.ReactNode;
  }>,
) {
  return (
    <html lang="zh-CN" suppressHydrationWarning data-darkreader-ignore>
    <body className="h-screen overflow-hidden" suppressHydrationWarning>
    <SessionsProvider>
      <SidebarProvider
        style={{
          // eslint-disable-next-line @typescript-eslint/ban-ts-comment
          // @ts-expect-error
          '--sidebar-width': '300px',
          '--sidebar-width-icon': '300px',
        }}
      >
        {/* 左侧的面板 */}
        <LeftPanel/>
        {/* 右侧的内容 */}
        <div className="flex-1 bg-[#f8f8f7] h-screen overflow-hidden">
          {children}
        </div>
      </SidebarProvider>
    </SessionsProvider>
    <Toaster position="top-center" richColors/>
    </body>
    </html>
  )
}
