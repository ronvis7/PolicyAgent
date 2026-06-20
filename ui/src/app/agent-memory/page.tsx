'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { BrainCircuit, MessageSquareText, Sparkles, Trash2 } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Skeleton } from '@/components/ui/skeleton'
import { agentMemoryApi } from '@/lib/api'
import type { AgentMemoryItem } from '@/lib/api'

function formatDate(date: string) {
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return date
  return parsed.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}

export default function AgentMemoryPage() {
  const [memories, setMemories] = useState<AgentMemoryItem[]>([])
  const [loading, setLoading] = useState(true)
  // 二次确认与删除中状态（按条目 id）
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    agentMemoryApi
      .list()
      .then((res) => setMemories(res.items))
      .catch((err) => toast.error(err instanceof Error ? err.message : '加载 Agent 记忆失败'))
      .finally(() => setLoading(false))
  }, [])

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      await agentMemoryApi.remove(id)
      setMemories((prev) => prev.filter((m) => m.id !== id))
      toast.success('已删除该记忆')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '删除失败')
    } finally {
      setDeletingId(null)
      setConfirmingId(null)
    }
  }

  return (
    <div className="h-full overflow-hidden bg-[#f8f8f7]">
      <header className="flex min-h-16 items-center gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
        <div className="min-w-0">
          <h1 className="truncate font-serif text-lg font-semibold tracking-tight text-[#1c2127]">Agent 记忆</h1>
          <p className="hidden text-xs text-[#778090] sm:block">
            智能助手在历次对话中为本企业记下的长期记忆，会在新会话里被自动想起。
          </p>
        </div>
      </header>

      <div className="h-[calc(100vh-4rem)] overflow-auto p-4">
        <div className="mx-auto max-w-3xl space-y-6">
          <section className="rounded-[18px] border border-[#e5e2de] bg-white p-5 shadow-[0_10px_30px_rgba(16,24,40,.04)]">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-[#202939]">
              <BrainCircuit className="size-4 text-[#287174]" />
              长期记忆
            </div>
            <p className="mb-4 text-xs leading-6 text-[#778090]">
              当你在对话中告诉助手值得长期记住的信息（如经营数据变化、申报意向、答复偏好），
              助手会主动把要点记入这里；下次开启新会话时它会自动想起这些内容，无需你重复说明。
              你可以随时删除不再需要的记忆。
            </p>

            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-2xl" />
                ))}
              </div>
            ) : memories.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-center">
                <div className="flex size-12 items-center justify-center rounded-full bg-brand-50 text-[#287174]">
                  <Sparkles className="size-5" />
                </div>
                <div className="text-sm font-medium text-[#344054]">还没有任何长期记忆</div>
                <p className="max-w-sm text-xs leading-6 text-[#778090]">
                  在对话中向助手介绍你的企业近况或偏好，例如“我们今年新增了 3 项发明专利”、
                  “以后回答请简洁些”，助手会自动把要点记下来。
                </p>
              </div>
            ) : (
              <ul className="space-y-2.5">
                {memories.map((memory) => (
                  <li
                    key={memory.id}
                    className="group flex items-start gap-3 rounded-2xl border border-[#e7e4df] bg-[#fafafa] p-4 transition-all hover:border-brand-200 hover:bg-white hover:shadow-[var(--shadow-card)]"
                  >
                    <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-[#287174]">
                      <MessageSquareText className="size-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm leading-6 text-[#202939]">{memory.content}</p>
                      <p className="mt-1 text-[11px] text-[#98a2b3]">记于 {formatDate(memory.created_at)}</p>
                    </div>
                    {confirmingId === memory.id ? (
                      <div className="flex shrink-0 items-center gap-2 text-xs">
                        <button
                          type="button"
                          disabled={deletingId === memory.id}
                          onClick={() => handleDelete(memory.id)}
                          className="rounded-lg bg-[#d92d20] px-2.5 py-1 font-medium text-white hover:bg-[#b42318] disabled:opacity-60"
                        >
                          {deletingId === memory.id ? '删除中…' : '确认删除'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmingId(null)}
                          className="rounded-lg px-2 py-1 text-[#667085] hover:bg-[#f2f4f7]"
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        aria-label="删除记忆"
                        onClick={() => setConfirmingId(memory.id)}
                        className="shrink-0 rounded-lg p-1.5 text-[#98a2b3] opacity-0 transition-opacity hover:bg-[#fef3f2] hover:text-[#d92d20] group-hover:opacity-100"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
