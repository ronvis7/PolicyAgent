'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import { AlarmClock, CheckCircle2, ExternalLink, FileDown, Loader2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
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
import { feedApi, policyApi, qualificationApi, reportApi } from '@/lib/api'
import type {
  FeedItem,
  FeedStatus,
  PolicyDetail,
  QualificationDetail,
  SettableFeedStatus,
} from '@/lib/api'
import { QualificationDetailView } from '@/components/qualification-detail'
import { FEED_UNREAD_CHANGED_EVENT } from '@/lib/feed-events'

const PAGE_SIZE = 50

/** 状态筛选项（空串=全部） */
const FILTERS: { label: string; value: FeedStatus | '' }[] = [
  { label: '全部', value: '' },
  { label: '未读', value: 'unread' },
  { label: '已申报', value: 'applied' },
  { label: '已忽略', value: 'ignored' },
]

/** 机会类型分栏（空串=全部）：把政策/资质/赛事分开看，避免混在一个列表 */
type OpportunityType = 'policy' | 'qualification' | 'competition'
const TYPE_TABS: { label: string; value: OpportunityType | '' }[] = [
  { label: '全部机会', value: '' },
  { label: '政策机会', value: 'policy' },
  { label: '资质机会', value: 'qualification' },
  { label: '赛事机会', value: 'competition' },
]

const STATUS_LABEL: Record<FeedStatus, string> = {
  unread: '新',
  read: '已读',
  applied: '已申报',
  ignored: '已忽略',
}

/** 临期提醒阈值（天）：≤3 天标红、≤14 天标琥珀，与后端默认窗口一致 */
const DEADLINE_URGENT_DAYS = 3
const DEADLINE_SOON_DAYS = 14

/** 申报截止徽章：依抽取状态/剩余天数渲染，截止日期以政策原文为准。 */
function DeadlineBadge({ item }: { item: FeedItem }) {
  // 仅政策类有截止概念；资质走目录，无此字段
  if (item.type === 'qualification') return null

  if (item.deadline_status === 'extracted' && item.days_left !== null) {
    const d = item.days_left
    const label =
      d < 0 ? '已过期' : d === 0 ? '今天截止' : `还剩 ${d} 天截止`
    const tone =
      d < 0
        ? 'border-muted text-muted-foreground line-through'
        : d <= DEADLINE_URGENT_DAYS
          ? 'border-red-400 text-red-600 dark:text-red-400'
          : d <= DEADLINE_SOON_DAYS
            ? 'border-amber-400 text-amber-600 dark:text-amber-400'
            : 'border-muted text-muted-foreground'
    return (
      <Badge variant="outline" className={`mt-0.5 shrink-0 gap-1 ${tone}`} title={`申报截止：${item.apply_deadline}（以原文为准）`}>
        <AlarmClock className="size-3" />
        {label}
      </Badge>
    )
  }
  if (item.deadline_status === 'rolling') {
    return (
      <Badge variant="outline" className="mt-0.5 shrink-0 text-muted-foreground" title="常年受理/无固定截止">
        常年受理
      </Badge>
    )
  }
  return null
}

/** 工作台 Feed 页（④）：持久化的可申报政策信息流 + 状态流转 + 重新匹配。 */
export default function FeedPage() {
  const router = useRouter()

  const [filter, setFilter] = useState<FeedStatus | ''>('')
  const [typeFilter, setTypeFilter] = useState<OpportunityType | ''>('')
  const [items, setItems] = useState<FeedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [recomputing, setRecomputing] = useState(false)
  const [exporting, setExporting] = useState(false)

  const [detail, setDetail] = useState<PolicyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 资质详情（type=qualification 的条目走资质详情，policy_id 即资质 key）
  const [qualDetail, setQualDetail] = useState<QualificationDetail | null>(null)
  const [qualDetailLoading, setQualDetailLoading] = useState(false)

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

  /** 导出政策匹配简报 PDF（组装当前租户匹配/差距/临期，复用 PR #44 带鉴权下载） */
  const onExport = async () => {
    setExporting(true)
    try {
      const { blob, filename } = await reportApi.downloadBrief()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('简报已导出')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '导出简报失败')
    } finally {
      setExporting(false)
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

  /** 按机会类型分流：资质走资质详情，其余(政策)走公开政策详情 */
  const openDetail = async (item: FeedItem) => {
    if (item.type === 'qualification') {
      setQualDetailLoading(true)
      setQualDetail(null)
      try {
        setQualDetail(await qualificationApi.getDetail(item.policy_id))
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '获取资质详情失败')
      } finally {
        setQualDetailLoading(false)
      }
      return
    }
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await policyApi.get(item.policy_id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '获取政策详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  // 类型分栏在前端按已加载列表过滤（状态过滤走服务端）；政策 tab 兜底吃掉未知类型，避免新类型条目"消失"
  const visibleItems = typeFilter
    ? items.filter((m) =>
        typeFilter === 'policy'
          ? m.type !== 'qualification' && m.type !== 'competition'
          : m.type === typeFilter,
      )
    : items

  return (
    <div className="h-full flex flex-col bg-[#f8f8f7]">
      {/* 头部 */}
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <div className="min-w-0">
            <h1 className="truncate font-serif text-lg font-semibold tracking-tight text-[#1c2127]">工作台</h1>
            <p className="hidden text-xs text-[#778090] sm:block">
              系统依据企业档案持续盯紧可申报机会，有新增会顶到这里。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            className="cursor-pointer rounded-xl bg-white"
            onClick={onExport}
            disabled={exporting}
            title="把当前匹配政策、资质差距与临期提醒导出为 PDF 简报"
          >
            {exporting ? <Loader2 className="size-4 animate-spin" /> : <FileDown className="size-4" />}
            导出简报
          </Button>
          <Button
            variant="outline"
            className="cursor-pointer rounded-xl bg-white"
            onClick={onRecompute}
            disabled={recomputing}
          >
            {recomputing ? <Loader2 className="size-4 animate-spin" /> : null}
            重新匹配
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-[900px] mx-auto">
          {/* 机会类型分栏：政策 / 资质分开看 */}
          <div className="mb-3 inline-flex rounded-xl border border-[#e5e2de] bg-white p-1">
            {TYPE_TABS.map((t) => (
              <button
                key={t.value || 'all'}
                type="button"
                className={cn(
                  'cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                  typeFilter === t.value
                    ? 'bg-primary text-white shadow-[var(--shadow-card)]'
                    : 'text-[#667085] hover:bg-[#f2f1ef]',
                )}
                onClick={() => setTypeFilter(t.value)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* 状态筛选 */}
          <div className="mb-4 flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <Button
                key={f.value || 'all'}
                size="sm"
                variant={filter === f.value ? 'default' : 'outline'}
                className={cn('cursor-pointer rounded-full', filter !== f.value && 'bg-white')}
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
          ) : visibleItems.length === 0 ? (
            <div className="rounded-[18px] border border-[#e5e2de] bg-white py-20 text-center text-sm text-[#778090] shadow-[0_10px_30px_rgba(16,24,40,.04)]">
              <p>{typeFilter ? '该分类下暂无可申报机会。' : '暂无可申报机会。'}</p>
              {items.length === 0 && (
                <p className="mt-2">
                  请先完善
                  <Button
                    variant="link"
                    className="px-1 cursor-pointer text-[#287174]"
                    onClick={() => router.push('/enterprise-profile')}
                  >
                    企业档案
                  </Button>
                  ，并确保公开政策库已抓取入库；或点右上角「重新匹配」。
                </p>
              )}
            </div>
          ) : (
            <ul className="space-y-3">
              {visibleItems.map((m) => (
                <li
                  key={m.id}
                  className="group relative overflow-hidden rounded-2xl border border-[#e7e4df] bg-white p-4 pl-5 shadow-[var(--shadow-card)] transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-hover)]"
                >
                  {/* 机会类型左侧彩条：资质=翠绿、赛事=紫罗兰、政策=品牌青绿 */}
                  <span
                    className={cn(
                      'absolute left-0 top-0 h-full w-1',
                      m.type === 'qualification'
                        ? 'bg-emerald-400'
                        : m.type === 'competition'
                          ? 'bg-violet-400'
                          : 'bg-primary',
                    )}
                  />
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
                    {/* 机会类型徽章：资质/赛事区别于政策 */}
                    <Badge
                      variant="outline"
                      className={`mt-0.5 shrink-0 ${
                        m.type === 'qualification'
                          ? 'border-emerald-300 text-emerald-700 dark:text-emerald-400'
                          : m.type === 'competition'
                            ? 'border-violet-300 text-violet-700 dark:text-violet-400'
                            : 'text-muted-foreground'
                      }`}
                    >
                      {m.type === 'qualification' ? '资质' : m.type === 'competition' ? '赛事' : '政策'}
                    </Badge>
                    {/* 申报截止徽章（主线⑤；临期标红/琥珀） */}
                    <DeadlineBadge item={m} />
                    <button
                      type="button"
                      className="text-left font-semibold leading-snug text-[#287174] line-clamp-2 cursor-pointer hover:underline"
                      onClick={() => openDetail(m)}
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
                        <span className="inline-flex items-center gap-1.5" title="结构化命中归一化分">
                          命中度
                          <span className="h-1.5 w-12 overflow-hidden rounded-full bg-[#eceae6]">
                            <span
                              className="block h-full rounded-full bg-primary"
                              style={{ width: `${Math.min(100, m.structured_score * 100)}%` }}
                            />
                          </span>
                          {(m.structured_score * 100).toFixed(0)}%
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
              {/* 申报截止（主线⑤；LLM 抽取，以原文为准、供参考核对） */}
              {detail.deadline_status !== 'unknown' && (
                <div className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/20 px-3 py-2 text-sm">
                  <div className="flex items-center gap-1.5 font-medium text-amber-700 dark:text-amber-400">
                    <AlarmClock className="size-3.5" />
                    {detail.deadline_status === 'extracted'
                      ? `申报截止：${detail.apply_deadline}`
                      : '常年受理 / 无固定截止'}
                  </div>
                  {detail.apply_window_text && (
                    <p className="mt-1 text-muted-foreground">原文窗口：{detail.apply_window_text}</p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground">
                    截止日期由系统从正文自动抽取，可能存在偏差，请以政策原文与官方申报平台为准。
                  </p>
                </div>
              )}
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

      {/* 资质详情弹窗（type=qualification） */}
      <Dialog
        open={qualDetailLoading || !!qualDetail}
        onOpenChange={(open) => !open && setQualDetail(null)}
      >
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
          {qualDetailLoading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : qualDetail ? (
            <>
              <DialogHeader>
                <DialogTitle className="text-left leading-relaxed">{qualDetail.name}</DialogTitle>
                <DialogDescription className="sr-only">资质详情</DialogDescription>
              </DialogHeader>
              <div className="overflow-auto flex-1">
                <QualificationDetailView detail={qualDetail} />
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
