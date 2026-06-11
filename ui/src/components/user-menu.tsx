'use client'

import React, {useState} from 'react'
import {useRouter} from 'next/navigation'
import {toast} from 'sonner'
import {LogOut} from 'lucide-react'
import {Avatar, AvatarFallback} from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {SidebarMenuButton} from '@/components/ui/sidebar'
import {useAuth} from '@/providers/auth-provider'

/** 取显示名或邮箱的首字母作为头像占位 */
function initialOf(name: string, email: string): string {
  const source = name.trim() || email.trim()
  return source ? source[0].toUpperCase() : '?'
}

/**
 * 用户菜单：展示当前用户与角色，提供登出入口
 */
export function UserMenu() {
  const {user, role, logout} = useAuth()
  const router = useRouter()
  const [loggingOut, setLoggingOut] = useState(false)

  if (!user) return null

  const handleLogout = async () => {
    if (loggingOut) return
    setLoggingOut(true)
    try {
      await logout()
      toast.success('已登出')
      router.replace('/login')
    } finally {
      setLoggingOut(false)
    }
  }

  const displayName = user.display_name || user.email

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton className="cursor-pointer">
          <Avatar className="size-7">
            <AvatarFallback className="text-xs">
              {initialOf(user.display_name, user.email)}
            </AvatarFallback>
          </Avatar>
          <span className="flex min-w-0 flex-col text-left">
            <span className="truncate text-sm font-medium">{displayName}</span>
            <span className="truncate text-xs text-muted-foreground">{role}</span>
          </span>
        </SidebarMenuButton>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-(--radix-dropdown-menu-trigger-width) min-w-56">
        <DropdownMenuLabel className="flex flex-col">
          <span className="truncate text-sm font-medium">{displayName}</span>
          <span className="truncate text-xs font-normal text-muted-foreground">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator/>
        <DropdownMenuItem
          className="cursor-pointer text-destructive focus:text-destructive"
          disabled={loggingOut}
          onSelect={(e) => {
            e.preventDefault()
            handleLogout()
          }}
        >
          <LogOut className="size-4"/>
          登出
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
