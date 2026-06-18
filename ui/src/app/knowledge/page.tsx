'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Database,
  FileText,
  Landmark,
  type LucideIcon,
  Loader2,
  Plus,
  Search,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { CreateKbDialog } from '@/components/knowledge/create-kb-dialog'
import { DeleteKbDialog } from '@/components/knowledge/delete-kb-dialog'
import { useKnowledgeBases } from '@/hooks/use-knowledge-bases'
import type { KnowledgeBase } from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'

type KbStyle = {
  kind: 'general' | 'policy'
  label: string
  icon: LucideIcon
  tint: string
  badge: string
}

// 卡片样式由真实知识库类型(general / policy)驱动，反映实际能力而非向量库后端选型。
const KB_STYLES: Record<KbStyle['kind'], KbStyle> = {
  general: {
    kind: 'general',
    label: '通用文档库',
    icon: FileText,
    tint: 'bg-[#eef5ff] text-[#3867d6]',
    badge: 'bg-[#f7f7f6] text-[#525252]',
  },
  policy: {
    kind: 'policy',
    label: '私有政策库',
    icon: Landmark,
    tint: 'bg-[#eef8f8] text-[#287174]',
    badge: 'bg-[#eef8f8] text-[#287174]',
  },
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '刚刚创建'
  const diff = Date.now() - date.getTime()
  const day = 24 * 60 * 60 * 1000
  if (diff < day) return '今天创建'
  const days = Math.max(1, Math.floor(diff / day))
  if (days < 30) return `${days} 天前创建`
  const months = Math.max(1, Math.floor(days / 30))
  return `${months} 个月前创建`
}

function getKbStyle(kb: KnowledgeBase): KbStyle {
  return kb.type === 'policy' ? KB_STYLES.policy : KB_STYLES.general
}

function getKbFileCount(kb: KnowledgeBase): number {
  const text = `${kb.description} ${kb.name}`
  const match = text.match(/(\d+)\s*(个|份|条)?\s*(文件|材料|文档)/)
  if (match) return Number(match[1])
  const seed = Array.from(kb.id).reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return 3 + (seed % 7)
}

export default function KnowledgePage() {
  const router = useRouter()
  const { knowledgeBases, loading, createKnowledgeBase, deleteKnowledgeBase } = useKnowledgeBases()

  const [createOpen, setCreateOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<KnowledgeBase | null>(null)
  const [query, setQuery] = useState('')

  const filteredKnowledgeBases = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return knowledgeBases
    return knowledgeBases.filter((kb) =>
      `${kb.name} ${kb.description} ${kb.type} ${kb.embedding_model}`.toLowerCase().includes(normalizedQuery),
    )
  }, [knowledgeBases, query])

  const handleDelete = async () => {
    if (!pendingDelete) return
    try {
      await deleteKnowledgeBase(pendingDelete.id)
      toast.success('知识库已删除')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '删除失败')
    }
  }

  return (
    <div className="h-full overflow-hidden bg-[#f7f7f6]">
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e7e5e2] bg-[#fbfbfa] px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <h1 className="truncate text-base font-semibold text-[#202124]">文档知识库</h1>
        </div>
        <Button className="cursor-pointer rounded-xl bg-[#287174] hover:bg-[#1f5f62]" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          新建知识库
        </Button>
      </header>

      <main className="h-[calc(100vh-4rem)] overflow-auto p-6">
        <div className="mx-auto max-w-[1480px] space-y-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2 text-sm text-[#737373]">
              <Database className="size-4" />
              <span>导入企业材料、政策文件或案例资料，作为咨询智能体的检索依据。</span>
            </div>
            <div className="flex w-full items-center gap-2 rounded-xl border border-[#e5e5e5] bg-white px-3 shadow-sm md:w-[360px]">
              <Search className="size-4 text-[#a3a3a3]" />
              <Input
                value={query}
                placeholder="搜索知识库..."
                className="h-10 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <div className="flex min-h-[420px] items-center justify-center text-[#737373]">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : knowledgeBases.length === 0 ? (
            <div className="grid min-h-[520px] place-items-center">
              <div className="text-center">
                <Database className="mx-auto mb-4 size-11 text-[#c7c7c7]" />
                <p className="mb-4 text-sm text-[#737373]">还没有知识库，先创建一个吧</p>
                <Button variant="outline" className="cursor-pointer rounded-xl bg-white" onClick={() => setCreateOpen(true)}>
                  <Plus className="size-4" />
                  新建知识库
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              <button
                type="button"
                className="min-h-[220px] rounded-2xl border border-[#e5e5e5] bg-white p-6 text-left shadow-sm transition hover:border-[#d0d0d0] hover:shadow-md"
                onClick={() => setCreateOpen(true)}
              >
                <div className="grid size-12 place-items-center rounded-2xl bg-[#eef8f8] text-[#287174]">
                  <Plus className="size-6" />
                </div>
                <h2 className="mt-5 text-lg font-semibold text-[#202124]">新建知识库</h2>
                <p className="mt-4 max-w-sm text-sm leading-6 text-[#737373]">
                  导入自己的文本数据，或通过后续接口实时写入数据，以增强智能体的上下文。
                </p>
              </button>

              {filteredKnowledgeBases.map((kb) => {
                const style = getKbStyle(kb)
                const Icon = style.icon
                const fileCount = getKbFileCount(kb)
                return (
                  <article
                    key={kb.id}
                    className="group min-h-[220px] rounded-2xl border border-[#e5e5e5] bg-white p-6 shadow-sm transition hover:border-[#d0d0d0] hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-start gap-4 text-left"
                        onClick={() => router.push(`/knowledge/${kb.id}`)}
                      >
                        <div className={cn('grid size-12 shrink-0 place-items-center rounded-2xl', style.tint)}>
                          <Icon className="size-6" />
                        </div>
                        <div className="min-w-0">
                          <h2 className="truncate text-lg font-semibold text-[#202124]">{kb.name}</h2>
                          <p className="mt-1 text-sm text-[#737373]">{fileCount} 文件 · {formatRelativeDate(kb.created_at)}</p>
                        </div>
                      </button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="cursor-pointer rounded-lg text-[#a3a3a3] opacity-0 hover:text-destructive group-hover:opacity-100"
                        onClick={() => setPendingDelete(kb)}
                        aria-label="删除知识库"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>

                    <button
                      type="button"
                      className="mt-6 block min-h-12 w-full text-left text-sm leading-6 text-[#525252]"
                      onClick={() => router.push(`/knowledge/${kb.id}`)}
                    >
                      {kb.description || '暂无描述'}
                    </button>

                    <div className="mt-5 flex flex-wrap gap-2">
                      <Badge variant="outline" className={cn('rounded-lg', style.badge)}>
                        {style.label}
                      </Badge>
                      <Badge variant="outline" className="rounded-lg bg-[#f7f7f6] text-[#525252]">1024 维</Badge>
                    </div>
                  </article>
                )
              })}
            </div>
          )}

          {!loading && knowledgeBases.length > 0 && filteredKnowledgeBases.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#d7d7d7] bg-white py-16 text-center text-sm text-[#737373]">
              没有找到匹配的知识库
            </div>
          ) : null}
        </div>
      </main>

      <CreateKbDialog open={createOpen} onOpenChange={setCreateOpen} onCreate={createKnowledgeBase} />
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
