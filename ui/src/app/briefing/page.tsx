'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, ArrowRight, RefreshCw, Radar, Sparkles } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { briefingApi } from '@/lib/api'
import type { Briefing, BriefingUrgency } from '@/lib/api'

function formatDateTime(value: string | null) {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { dateStyle: 'long', timeStyle: 'short' })
}

// 类别 → 徽章配色
const CATEGORY_STYLE: Record<string, string> = {
  临期申报: 'bg-[#fef3f2] text-[#b42318] border-[#fecdca]',
  政策机会: 'bg-brand-50 text-[#287174] border-brand-200',
  资质机会: 'bg-[#fff8e8] text-[#8a6d3b] border-[#f2e6c2]',
}

const URGENCY_DOT: Record<BriefingUrgency, string> = {
  high: 'bg-[#d92d20]',
  normal: 'bg-[#287174]',
  low: 'bg-[#98a2b3]',
}

export default function BriefingPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    briefingApi
      .latest()
      .then(setBriefing)
      .catch((err) => toast.error(err instanceof Error ? err.message : '加载情报简报失败'))
      .finally(() => setLoading(false))
  }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const result = await briefingApi.generate()
      setBriefing(result)
      toast.success('情报简报已生成')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const hasBriefing = briefing?.has_briefing && briefing.items.length > 0

  return (
    <div className="h-full overflow-hidden bg-[#f8f8f7]">
      <header className="flex min-h-16 items-center gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-serif text-lg font-semibold tracking-tight text-[#1c2127]">情报简报</h1>
          <p className="hidden text-xs text-[#778090] sm:block">
            助手会定时主动扫描与你匹配的政策、资质与临期申报，归纳成带理由的机会简报。
          </p>
        </div>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[#287174] px-3.5 py-2 text-sm font-medium text-white shadow-[var(--shadow-card)] transition-colors hover:bg-[#1f5a5c] disabled:opacity-60"
        >
          <RefreshCw className={`size-4 ${generating ? 'animate-spin' : ''}`} />
          {generating ? '生成中…' : '立即生成'}
        </button>
      </header>

      <div className="h-[calc(100vh-4rem)] overflow-auto p-4">
        <div className="mx-auto max-w-3xl space-y-4">
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-20 w-full rounded-[18px]" />
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full rounded-2xl" />
              ))}
            </div>
          ) : !hasBriefing ? (
            <div className="flex flex-col items-center gap-3 rounded-[18px] border border-[#e5e2de] bg-white py-16 text-center shadow-[0_10px_30px_rgba(16,24,40,.04)]">
              <div className="flex size-12 items-center justify-center rounded-full bg-brand-50 text-[#287174]">
                <Radar className="size-5" />
              </div>
              <div className="text-sm font-medium text-[#344054]">还没有情报简报</div>
              <p className="max-w-sm text-xs leading-6 text-[#778090]">
                完善企业档案、抓取一些公开政策后，点右上角「立即生成」，助手会为你筛出最值得关注的机会；
                之后它也会每天自动刷新。
              </p>
            </div>
          ) : (
            <>
              {/* 总览卡 */}
              <section className="rounded-[18px] border border-brand-200 bg-gradient-to-br from-brand-50 to-white p-5 shadow-[0_10px_30px_rgba(16,24,40,.04)]">
                <div className="flex items-center gap-2 text-xs font-medium text-[#287174]">
                  <Sparkles className="size-3.5" />
                  {briefing!.generated_by === 'llm' ? 'AI 归纳' : '规则归纳'}
                  {briefing!.generated_at && <span className="text-[#98a2b3]">· {formatDateTime(briefing!.generated_at)}</span>}
                </div>
                <p className="mt-1.5 font-serif text-lg font-semibold leading-7 text-[#1c2127]">
                  {briefing!.headline}
                </p>
              </section>

              {/* 情报项 */}
              <ul className="space-y-2.5">
                {briefing!.items.map((item, idx) => (
                  <li
                    key={`${item.title}-${idx}`}
                    className="rounded-2xl border border-[#e7e4df] bg-white p-4 shadow-[0_6px_18px_rgba(16,24,40,.03)] transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)]"
                  >
                    <div className="flex items-start gap-2.5">
                      <span className={`mt-1.5 size-2 shrink-0 rounded-full ${URGENCY_DOT[item.urgency]}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-[#202939]">{item.title}</span>
                          {item.category && (
                            <Badge
                              variant="outline"
                              className={`rounded-full border text-[11px] ${CATEGORY_STYLE[item.category] ?? ''}`}
                            >
                              {item.category}
                            </Badge>
                          )}
                        </div>
                        {item.reason && <p className="mt-1.5 text-xs leading-6 text-[#566070]">{item.reason}</p>}
                        {item.action && (
                          <p className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-[#287174]">
                            <ArrowRight className="size-3.5" />
                            {item.action}
                          </p>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>

              {briefing!.disclaimer && (
                <div className="flex items-start gap-2 rounded-2xl border border-[#f2e6c2] bg-[#fff8e8] p-3 text-xs leading-6 text-[#8a6d3b]">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                  <span>{briefing!.disclaimer}</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
