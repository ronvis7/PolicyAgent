'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Database, Loader2, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { CreateKbDialog } from '@/components/knowledge/create-kb-dialog'
import { DeleteKbDialog } from '@/components/knowledge/delete-kb-dialog'
import { useKnowledgeBases } from '@/hooks/use-knowledge-bases'
import type { KnowledgeBase } from '@/lib/api/knowledge'

/** 格式化为本地日期 */
function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleDateString()
}

/**
 * 知识库管理页：列出当前租户的知识库，支持新建、删除、进入详情。
 * 独立于聊天模块（ADR-002）。
 */
export default function KnowledgePage() {
  const router = useRouter()
  const {
    knowledgeBases,
    loading,
    createKnowledgeBase,
    deleteKnowledgeBase,
  } = useKnowledgeBases()

  const [createOpen, setCreateOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<KnowledgeBase | null>(null)

  const handleDelete = async () => {
    if (!pendingDelete) return
    try {
      await deleteKnowledgeBase(pendingDelete.id)
      toast.success('知识库已删除')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <header className="flex justify-between items-center w-full py-2 px-4 border-b">
        <div className="flex items-center gap-2">
          <SidebarTrigger className="cursor-pointer" />
          <h1 className="text-base font-semibold">知识库</h1>
        </div>
        <Button className="cursor-pointer" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          新建知识库
        </Button>
      </header>

      {/* 列表 */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : knowledgeBases.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
            <Database className="size-10 mb-3 opacity-40" />
            <p className="mb-4">还没有知识库，先创建一个吧</p>
            <Button
              variant="outline"
              className="cursor-pointer"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="size-4" />
              新建知识库
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 max-w-[1200px] mx-auto">
            {knowledgeBases.map((kb) => (
              <div
                key={kb.id}
                className="group relative flex flex-col rounded-lg border bg-white p-4 hover:shadow-sm transition-shadow cursor-pointer"
                onClick={() => router.push(`/knowledge/${kb.id}`)}
              >
                <div className="flex items-start gap-2">
                  <Database className="size-5 mt-0.5 text-muted-foreground shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{kb.name}</div>
                    <p className="text-sm text-muted-foreground line-clamp-2 mt-1 min-h-[2.5rem]">
                      {kb.description || '暂无描述'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
                  <span>创建于 {formatDate(kb.created_at)}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="cursor-pointer opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      setPendingDelete(kb)
                    }}
                    aria-label="删除知识库"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <CreateKbDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={createKnowledgeBase}
      />
      <DeleteKbDialog
        open={pendingDelete !== null}
        kbName={pendingDelete?.name ?? ''}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        onConfirm={handleDelete}
      />
    </div>
  )
}
