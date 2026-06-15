'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import { ExternalLink, Loader2, Sparkles } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { policyApi } from '@/lib/api'
import type { PolicyDetail, PolicyMatchItem } from '@/lib/api'

const TOP_K = 20

/** 政策匹配页（③）：按当前企业档案即时匹配公开政策候选，展示分数与推荐理由。 */
export default function MatchesPage() {
  const router = useRouter()

  const [items, setItems] = useState<PolicyMatchItem[]>([])
  const [loading, setLoading] = useState(true)

  const [detail, setDetail] = useState<PolicyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const fetchMatches = useCallback(() => {
    setLoading(true)
    policyApi
      .match(TOP_K)
      .then((res) => setItems(res.items))
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : '获取政策匹配失败')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchMatches()
  }, [fetchMatches])

  const openDetail = async (id: string) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await policyApi.get(id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '获取政策详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <header className="flex justify-between items-center w-full py-2 px-4 border-b">
        <div className="flex items-center gap-2">
          <SidebarTrigger className="cursor-pointer" />
          <h1 className="text-base font-semibold">政策匹配</h1>
        </div>
        <Button variant="outline" className="cursor-pointer" onClick={fetchMatches} disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin" /> : null}
          重新匹配
        </Button>
      </header>

      {/* 候选列表 */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-[900px] mx-auto">
          <div className="mb-4 flex items-center gap-2 text-muted-foreground">
            <Sparkles className="size-5" />
            <span className="text-sm">
              依据企业档案（关键词/技术域/资质/行业）结合语义相似度，为您匹配可申报政策候选。
            </span>
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-20 text-center text-muted-foreground text-sm">
              <p>暂无匹配的政策候选。</p>
              <p className="mt-2">
                请先完善
                <Button
                  variant="link"
                  className="px-1 cursor-pointer"
                  onClick={() => router.push('/enterprise-profile')}
                >
                  企业档案
                </Button>
                的行业、关键词、技术域等信息，并确保公开政策库已抓取入库。
              </p>
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((m, idx) => (
                <li
                  key={m.policy.id}
                  className="rounded-lg border p-4 cursor-pointer hover:border-primary/50 hover:bg-accent/40 transition-colors"
                  onClick={() => openDetail(m.policy.id)}
                >
                  <div className="flex items-start gap-2 mb-1">
                    <Badge variant="secondary" className="mt-0.5 shrink-0">
                      #{idx + 1}
                    </Badge>
                    <div className="font-medium line-clamp-2">{m.policy.title}</div>
                  </div>

                  {/* 推荐理由 */}
                  {m.reasons.length > 0 && (
                    <ul className="mb-2 space-y-0.5 pl-1">
                      {m.reasons.map((r, i) => (
                        <li key={i} className="text-xs text-muted-foreground">
                          · {r}
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {m.policy.publish_date && <span>{m.policy.publish_date}</span>}
                    {m.policy.issuer && <Badge variant="outline">{m.policy.issuer}</Badge>}
                    {m.structured_score > 0 && (
                      <span title="结构化命中归一化分">
                        命中度 {(m.structured_score * 100).toFixed(0)}%
                      </span>
                    )}
                    {m.semantic_score > 0 && (
                      <span title="语义相似度">语义 {m.semantic_score.toFixed(2)}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* 详情弹窗 */}
      <Dialog open={detailLoading || !!detail} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          {detailLoading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : detail ? (
            <>
              <DialogHeader>
                <DialogTitle className="text-left leading-relaxed">{detail.title}</DialogTitle>
                <DialogDescription className="flex flex-wrap items-center gap-2 pt-1">
                  {detail.publish_date && <span>{detail.publish_date}</span>}
                  {detail.issuer && <Badge variant="secondary">{detail.issuer}</Badge>}
                  {detail.status && <Badge variant="outline">{detail.status}</Badge>}
                  {detail.doc_number && <span>文号：{detail.doc_number}</span>}
                </DialogDescription>
              </DialogHeader>
              <div className="overflow-auto flex-1 whitespace-pre-wrap text-sm leading-7 text-foreground/90">
                {detail.body_text || '（暂无正文，请查看原文链接）'}
              </div>
              {detail.source_url && (
                <a
                  href={detail.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  <ExternalLink className="size-3.5" />
                  查看原文
                </a>
              )}
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
