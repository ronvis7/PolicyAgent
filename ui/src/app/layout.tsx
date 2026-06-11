import React from 'react'
import type {Metadata} from 'next'
import {AuthProvider} from '@/providers/auth-provider'
import {AppShell} from '@/components/app-shell'
import {Toaster} from '@/components/ui/sonner'
import './globals.css'

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
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
    <Toaster position="top-center" richColors/>
    </body>
    </html>
  )
}
