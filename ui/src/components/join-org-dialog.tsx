'use client'

import {useEffect, useState} from 'react'
import {toast} from 'sonner'
import {Loader2, Search} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {Input} from '@/components/ui/input'
import {Button} from '@/components/ui/button'
import {ApiError, authApi, membershipApi} from '@/lib/api'
import type {OrgOption} from '@/lib/api'

type JoinOrgDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * 「加入其他组织」对话框
 *
 * 已登录用户搜索共享组织并提交加入申请（待对方 owner/admin 审批），无需新建账号。
 * 批准后该组织会出现在组织切换器中。
 */
export function JoinOrgDialog({open, onOpenChange}: JoinOrgDialogProps) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState<OrgOption[]>([])
  const [searching, setSearching] = useState(false)
  const [submittingId, setSubmittingId] = useState<string | null>(null)

  // 打开时重置，关闭时清理
  useEffect(() => {
    if (!open) {
      setQuery('')
      setOptions([])
      setSubmittingId(null)
    }
  }, [open])

  // 防抖检索可加入的共享组织
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setSearching(true)
    const timer = setTimeout(() => {
      authApi
        .listOrgs(query)
        .then((data) => {
          if (!cancelled) setOptions(data?.orgs ?? [])
        })
        .catch(() => {
          if (!cancelled) setOptions([])
        })
        .finally(() => {
          if (!cancelled) setSearching(false)
        })
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [open, query])

  const handleJoin = async (org: OrgOption) => {
    if (submittingId) return
    setSubmittingId(org.id)
    try {
      await membershipApi.requestJoin(org.id)
      toast.success(`已向「${org.name}」提交加入申请，待对方管理员审批`)
      onOpenChange(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.msg : '提交加入申请失败')
    } finally {
      setSubmittingId(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>加入其他组织</DialogTitle>
          <DialogDescription>
            搜索组织并提交加入申请，对方管理员批准后即可在左下角切换。无需新建账号。
          </DialogDescription>
        </DialogHeader>

        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"/>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入组织名搜索，例如：重庆理工大学"
            className="pl-8"
            autoFocus
          />
        </div>

        <div className="max-h-72 overflow-auto">
          {searching ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="size-4 animate-spin"/>
            </div>
          ) : options.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              没有匹配的组织
            </p>
          ) : (
            <ul className="space-y-1">
              {options.map((org) => (
                <li
                  key={org.id}
                  className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-accent"
                >
                  <span className="truncate text-sm">{org.name}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="cursor-pointer shrink-0"
                    disabled={submittingId !== null}
                    onClick={() => handleJoin(org)}
                  >
                    {submittingId === org.id ? <Loader2 className="size-3.5 animate-spin"/> : null}
                    申请加入
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
