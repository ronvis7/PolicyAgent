'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { BookOpen, Check, ChevronsUpDown, Loader2 } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { knowledgeApi, type KnowledgeBase } from '@/lib/api/knowledge'
import { sessionApi } from '@/lib/api/session'
import { ApiError } from '@/lib/api'

interface KnowledgeScopeSelectorProps {
  /** 当前会话 ID */
  sessionId: string
  /** 当前会话绑定的知识库 id（null/undefined 表示全库检索） */
  value?: string | null
  /** 是否禁用（如任务运行中） */
  disabled?: boolean
}

/**
 * 会话级知识库检索范围选择器
 *
 * 让用户把当前会话的检索范围硬限定到某个知识库，或恢复为「全部知识库」。
 * 选定后后端将绑定写入会话，检索工具据此硬限定范围（见 ADR-002，绑定优先于
 * Agent 自选）。知识库列表在首次展开下拉时按需加载，避免无谓请求。
 */
export function KnowledgeScopeSelector({ sessionId, value, disabled }: KnowledgeScopeSelectorProps) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(false)
  const [binding, setBinding] = useState(false)
  const [boundId, setBoundId] = useState<string | null>(value ?? null)

  // 同步外部传入的初始绑定（会话切换/详情刷新时）
  useEffect(() => {
    setBoundId(value ?? null)
  }, [value])

  // 首次展开下拉时按需加载知识库列表
  const loadKnowledgeBases = async () => {
    if (kbs.length > 0 || loading) return
    setLoading(true)
    try {
      setKbs(await knowledgeApi.listKnowledgeBases())
    } catch {
      toast.error('加载知识库列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelect = async (kbId: string | null) => {
    if (kbId === boundId || binding) return

    const prev = boundId
    setBoundId(kbId) // 乐观更新
    setBinding(true)
    try {
      await sessionApi.bindKnowledgeBase(sessionId, kbId)
      toast.success(kbId ? '已限定检索范围至该知识库' : '已恢复全库检索')
    } catch (error) {
      setBoundId(prev) // 失败回滚
      toast.error(error instanceof ApiError ? error.msg : '设置知识库范围失败')
    } finally {
      setBinding(false)
    }
  }

  const boundKb = kbs.find((kb) => kb.id === boundId) ?? null
  const label = boundId ? (boundKb?.name ?? '指定知识库') : '全部知识库'

  return (
    <DropdownMenu onOpenChange={(open) => { if (open) loadKnowledgeBases() }}>
      <DropdownMenuTrigger asChild disabled={disabled || binding}>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 rounded-full text-xs text-gray-600"
        >
          {binding ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <BookOpen className="size-3.5" />
          )}
          <span className="max-w-32 truncate">{label}</span>
          <ChevronsUpDown className="size-3 opacity-60" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="min-w-56">
        <DropdownMenuLabel className="text-xs text-muted-foreground">检索范围</DropdownMenuLabel>
        <DropdownMenuSeparator />

        <DropdownMenuItem className="cursor-pointer" onSelect={() => handleSelect(null)}>
          <span className="truncate">全部知识库</span>
          {boundId === null && <Check className="ml-auto size-4" />}
        </DropdownMenuItem>

        {loading && (
          <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            加载中...
          </div>
        )}

        {!loading && kbs.length === 0 && (
          <div className="px-2 py-1.5 text-xs text-muted-foreground">暂无知识库</div>
        )}

        {kbs.map((kb) => (
          <DropdownMenuItem key={kb.id} className="cursor-pointer" onSelect={() => handleSelect(kb.id)}>
            <span className="truncate">{kb.name}</span>
            {boundId === kb.id && <Check className="ml-auto size-4" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
