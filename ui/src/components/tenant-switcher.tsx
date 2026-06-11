'use client'

import React, {useState} from 'react'
import {toast} from 'sonner'
import {Check, ChevronsUpDown, Loader2} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {SidebarMenuButton} from '@/components/ui/sidebar'
import {ApiError} from '@/lib/api'
import {useAuth} from '@/providers/auth-provider'

/**
 * 组织（租户）切换器
 *
 * 展示当前激活组织，下拉可切换到其他有成员关系的组织。
 * 切换成功后令牌重签，AppShell 以 activeTenantId 为 key 重挂载并重载该组织数据。
 */
export function TenantSwitcher() {
  const {tenants, activeTenantId, switchTenant} = useAuth()
  const [switching, setSwitching] = useState(false)

  const activeTenant = tenants.find((t) => t.id === activeTenantId) ?? null
  const onlyOneTenant = tenants.length <= 1

  const handleSelect = async (tenantId: string) => {
    if (tenantId === activeTenantId || switching) return

    setSwitching(true)
    try {
      await switchTenant(tenantId)
      toast.success('已切换组织')
    } catch (error) {
      const message = error instanceof ApiError ? error.msg : '切换组织失败'
      toast.error(message)
    } finally {
      setSwitching(false)
    }
  }

  const triggerLabel = activeTenant?.name ?? '未选择组织'

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild disabled={onlyOneTenant || switching}>
        <SidebarMenuButton className="cursor-pointer justify-between">
          <span className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-medium">{triggerLabel}</span>
            {activeTenant && (
              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                {activeTenant.plan}
              </span>
            )}
          </span>
          {switching ? (
            <Loader2 className="size-4 shrink-0 animate-spin"/>
          ) : (
            !onlyOneTenant && <ChevronsUpDown className="size-4 shrink-0 opacity-60"/>
          )}
        </SidebarMenuButton>
      </DropdownMenuTrigger>

      {!onlyOneTenant && (
        <DropdownMenuContent align="start" className="w-(--radix-dropdown-menu-trigger-width) min-w-56">
          <DropdownMenuLabel className="text-xs text-muted-foreground">切换组织</DropdownMenuLabel>
          <DropdownMenuSeparator/>
          {tenants.map((tenant) => (
            <DropdownMenuItem
              key={tenant.id}
              className="cursor-pointer"
              onSelect={() => handleSelect(tenant.id)}
            >
              <span className="truncate">{tenant.name}</span>
              {tenant.id === activeTenantId && <Check className="ml-auto size-4"/>}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      )}
    </DropdownMenu>
  )
}
