'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import { CheckCircle2, ExternalLink, Loader2, LayoutDashboard, XCircle } from 'lucide-react'
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
import { feedApi, policyApi } from '@/lib/api'
import type { FeedItem, FeedStatus, PolicyDetail, SettableFeedStatus } from '@/lib/api'
import { FEED_UNREAD_CHANGED_EVENT } from '@/lib/feed-events'

const PAGE_SIZE = 50

/** 状态筛选项（空串=全部） */
const FILTERS: { label: string; value: FeedStatus | '' }[] = [
  { label: '全部', value: '' },
  { label: '未读', value: 'unread' },
  { label: '已申报', value: 'applied' },
  { label: '已忽略', value: 'ignored' },
]

const STATUS_LABEL: Record<FeedStatus, string> = {
  unread: '新',
  read: '已读',
  applied: '已申报',
  ignored: '已忽略',
}

/** 工作台 Feed 页（④）：持久化的可申报政策信息流 + 状态流转 + 重新匹配。 */
export default function FeedPage() {
  const router = useRouter()

  const [filter, setFilter] = useState<FeedStatus | ''>('')
  const [items, setItems] = useState<FeedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [recomputing, setRecomputing] = useState(false)

  const [detail, setDetail] = useState<PolicyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  /** 通知左栏刷新未读红点 */
  const notifyUnreadChanged = useCallback(() => {
    window.dispatchEvent(new Event(FEED_UNREAD_CHANGED_EVENT))
  }, [])

  /** 拉取列表；clearUnread=true 时顺带把未读清掉（进入工作台即视为已看） */
  const load = useCallback(
    async (status: FeedStatus | '', clearUnread: boolean) => {
      setLoading(true)
      try {
        const res = await feedApi.list({ status, page: 1, page_size: PAGE_SIZE })
        setItems(res.items)
        if (clearUnread) {
          await feedApi.markRead()
          notifyUnreadChanged()
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '获取工作台失败')
      } finally {
        setLoading(false)
      }
    },
    [notifyUnreadChanged],
  )

  // 首次进入：按当前筛选加载并清未读
  useEffect(() => {
    load('', true)
  }, [load])

  const onFilter = (value: FeedStatus | '') => {
    setFilter(value)
    load(value, false)
  }

  const onRecompute = async () => {
    setRecomputing(true)
    try {
      const result = await feedApi.recompute()
      toast.success(`重算完成：新增 ${result.new} 条，更新 ${result.updated} 条`)
      await load(filter, true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '重新匹配失败')
    } finally {
      setRecomputing(false)
    }
  }

  const onSetStatus = async (item: FeedItem, status: SettableFeedStatus) => {
    try {
      const updated = await feedApi.setStatus(item.id, status)
      // 若当前在按状态筛选且条目已不符合，则从列表移除；否则就地更新
      setItems((prev) =>
        filter && filter !== updated.status
          ? prev.filter((i) => i.id !== updated.id)
          : prev.map((i) => (i.id === updated.id ? updated : i)),
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '更新状态失败')
    }
  }

  const openDetail = async (policyId: string) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await policyApi.get(policyId))
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
          <h1 className="text-base font-semibold">工作台</h1>
        </div>
        <Button
          variant="outline"
          className="cursor-pointer"
          onClick={onRecompute}
          disabled={recomputing}
        >
          {recomputing ? <Loader2 className="size-4 animate-spin" /> : null}
          重新匹配
        </Button>
      </header>

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-[900px] mx-auto">
          <div className="mb-4 flex items-center gap-2 text-muted-foreground">
            <LayoutDashboard className="size-5" />
            <span className="text-sm">
              系统依据企业档案持续盯紧可申报政策，有新增会顶到这里。抓取政策或更新档案后自动刷新。
            </span>
          </div>

          {/* 状态筛选 */}
          <div className="mb-4 flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <Button
                key={f.value || 'all'}
                size="sm"
                variant={filter === f.value ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => onFilter(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-28 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-20 text-center text-muted-foreground text-sm">
              <p>暂无可申报政策。</p>
              <p className="mt-2">
                请先完善
                <Button
                  variant="link"
                  className="px-1 cursor-pointer"
                  onClick={() => router.push('/enterprise-profile')}
                >
                  企业档案
                </Button>
                ，并确保公开政策库已抓取入库；或点右上角「重新匹配」。
              </p>
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((m) => (
                <li
                  key={m.id}
                  className="rounded-lg border p-4 transition-colors hover:border-primary/50"
                >
                  <div className="flex items-start gap-2 mb-1">
                    {m.status === 'unread' && (
                      <Badge className="mt-0.5 shrink-0">{STATUS_LABEL.unread}</Badge>
                    )}
                    {m.status === 'applied' && (
                      <Badge variant="secondary" className="mt-0.5 shrink-0">
                        {STATUS_LABEL.applied}
                      </Badge>
                    )}
                    {m.status === 'ignored' && (
                      <Badge variant="outline" className="mt-0.5 shrink-0 text-muted-foreground">
                        {STATUS_LABEL.ignored}
                      </Badge>
                    )}
                    <button
                      type="button"
                      className="text-left font-medium line-clamp-2 cursor-pointer hover:underline"
                      onClick={() => openDetail(m.policy_id)}
                    >
                      {m.title}
                    </button>
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

                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      {m.publish_date && <span>{m.publish_date}</span>}
                      {m.issuer && <Badge variant="outline">{m.issuer}</Badge>}
                      {m.structured_score > 0 && (
                        <span title="结构化命中归一化分">
                          命中度 {(m.structured_score * 100).toFixed(0)}%
                        </span>
                      )}
                      {m.semantic_score > 0 && (
                        <span title="语义相似度">语义 {m.semantic_score.toFixed(2)}</span>
                      )}
                    </div>

                    {/* 状态操作 */}
                    <div className="flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="cursor-pointer h-7 px-2 text-xs"
                        disabled={m.status === 'applied'}
                        onClick={() => onSetStatus(m, 'applied')}
                      >
                        <CheckCircle2 className="size-3.5" />
                        已申报
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="cursor-pointer h-7 px-2 text-xs text-muted-foreground"
                        disabled={m.status === 'ignored'}
                        onClick={() => onSetStatus(m, 'ignored')}
                      >
                        <XCircle className="size-3.5" />
                        忽略
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* 详情弹窗（复用公开政策详情） */}
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
