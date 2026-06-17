'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { QualificationDetailView } from '@/components/qualification-detail'
import { qualificationApi, QUALIFICATION_LEVEL_LABEL } from '@/lib/api'
import type { QualificationDetail, QualificationMatchItem } from '@/lib/api'

/** 资质机会页（⑥ 能力①）：按企业档案匹配可申报资质，标注可申报/接近 + 差距雏形。 */
export default function QualificationsPage() {
  const router = useRouter()

  const [items, setItems] = useState<QualificationMatchItem[]>([])
  const [eligibleCount, setEligibleCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const [detail, setDetail] = useState<QualificationDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await qualificationApi.listMatches()
      setItems(res.items)
      setEligibleCount(res.eligible_count)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '获取资质机会失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openDetail = async (key: string) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await qualificationApi.getDetail(key))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '获取资质详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <div className="h-full flex flex-col bg-[#f8f8f7]">
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-[#202939]">资质机会</h1>
            <p className="hidden text-xs text-[#778090] sm:block">
              依据企业档案匹配可申报资质，按「可申报优先」排序；条件为概要，具体以官方最新办法为准。
            </p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-[900px] mx-auto">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-[18px] border border-[#e5e2de] bg-white py-20 text-center text-sm text-[#778090] shadow-[0_10px_30px_rgba(16,24,40,.04)]">
              <p>暂无匹配的资质。</p>
              <p className="mt-2">
                请先完善
                <Button
                  variant="link"
                  className="px-1 cursor-pointer text-[#287174]"
                  onClick={() => router.push('/enterprise-profile')}
                >
                  企业档案
                </Button>
                （所在地区、行业、技术域、已有资质等），匹配会更准。
              </p>
            </div>
          ) : (
            <>
              <p className="mb-3 text-sm text-[#778090]">
                共 {items.length} 项适用，其中
                <span className="mx-1 font-semibold text-[#202939]">{eligibleCount}</span>
                项可申报。
              </p>
              <ul className="space-y-3">
                {items.map((q) => (
                  <li
                    key={q.key}
                    className="rounded-2xl border border-[#e5e2de] bg-white p-4 shadow-[0_10px_30px_rgba(16,24,40,.04)] transition hover:border-[#cdd5df]"
                  >
                    <div className="flex items-start gap-2 mb-1">
                      {q.eligible ? (
                        <Badge className="mt-0.5 shrink-0 bg-emerald-600 hover:bg-emerald-600">
                          可申报
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="mt-0.5 shrink-0 text-muted-foreground">
                          接近
                        </Badge>
                      )}
                      <button
                        type="button"
                        className="text-left font-semibold leading-snug text-[#287174] line-clamp-2 cursor-pointer hover:underline"
                        onClick={() => openDetail(q.key)}
                      >
                        {q.name}
                      </button>
                    </div>

                    {q.reasons.length > 0 && (
                      <ul className="mb-2 space-y-0.5 pl-1">
                        {q.reasons.map((r, i) => (
                          <li key={i} className="text-xs text-muted-foreground">
                            · {r}
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="secondary">
                        {QUALIFICATION_LEVEL_LABEL[q.level] ?? q.level}
                      </Badge>
                      {q.category && <Badge variant="outline">{q.category}</Badge>}
                      {q.region && <span>{q.region}</span>}
                      {q.issuer && <span>{q.issuer}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>

      {/* 资质详情弹窗 */}
      <Dialog open={detailLoading || !!detail} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
          {detailLoading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : detail ? (
            <>
              <DialogHeader>
                <DialogTitle className="text-left leading-relaxed flex items-center gap-2">
                  <CheckCircle2 className="size-5 shrink-0 text-emerald-600" />
                  {detail.name}
                </DialogTitle>
              </DialogHeader>
              <div className="overflow-auto flex-1">
                <QualificationDetailView detail={detail} />
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
