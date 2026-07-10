'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import {
  AlarmClock,
  ArrowLeft,
  Award,
  CheckCircle2,
  ChevronRight,
  DownloadCloud,
  ExternalLink,
  FileDown,
  FileText,
  Loader2,
  MapPin,
  Radar,
  Trophy,
  XCircle,
} from 'lucide-react'
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
  // 赛事机会下钻：null=展示地区聚合卡片，非空=展示该地区的比赛列表
  const [contestRegion, setContestRegion] = useState<string | null>(null)
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

  const NO_REGION_LABEL = '其他地区'

  // 赛事机会按地区聚合（数量降序），供两级视图第一级的地区卡片
  const contestRegionGroups = useMemo(() => {
    const counts = new Map<string, number>()
    for (const m of items) {
      if (m.type !== 'competition') continue
      const region = m.region || NO_REGION_LABEL
      counts.set(region, (counts.get(region) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([region, count]) => ({ region, count }))
      .sort((a, b) => b.count - a.count || a.region.localeCompare(b.region, 'zh'))
  }, [items])

  // 赛事 tab 未选地区时展示地区聚合网格；选了地区则下钻到该地区比赛列表
  const inContestGrid = typeFilter === 'competition' && contestRegion === null
  const renderItems =
    typeFilter === 'competition' && contestRegion !== null
      ? visibleItems.filter((m) => (m.region || NO_REGION_LABEL) === contestRegion)
      : visibleItems

  // 切换机会类型时重置赛事下钻状态，避免残留在某地区视图
  const onTypeTab = (value: OpportunityType | '') => {
    setTypeFilter(value)
    setContestRegion(null)
  }

  const unreadCount = items.filter((item) => item.status === 'unread').length
  const urgentCount = items.filter(
    (item) =>
      item.deadline_status === 'extracted' &&
      item.days_left !== null &&
      item.days_left >= 0 &&
      item.days_left <= DEADLINE_SOON_DAYS,
  ).length
  const competitionCount = items.filter((item) => item.type === 'competition').length

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border bg-background/90 px-4 backdrop-blur sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-card" />
          <span className="h-4 w-px bg-border" />
          <span className="text-xs font-medium tracking-wide text-muted-foreground">机会工作台</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="cursor-pointer rounded-lg bg-card"
            onClick={onExport}
            disabled={exporting}
            title="把当前匹配政策、资质差距与临期提醒导出为 PDF 简报"
          >
            {exporting ? <Loader2 className="size-4 animate-spin" /> : <FileDown className="size-4" />}
            导出简报
          </Button>
          <Button
            size="sm"
            className="cursor-pointer rounded-lg"
            onClick={onRecompute}
            disabled={recomputing}
          >
            {recomputing ? <Loader2 className="size-4 animate-spin" /> : null}
            重新匹配
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-[1120px] px-4 py-6 sm:px-6 sm:py-8">
          <section className="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_460px] lg:items-end">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-primary">
                <Radar className="size-4" />
                POLICY RADAR
              </div>
              <h1 className="max-w-2xl font-serif text-3xl font-medium leading-tight tracking-tight text-foreground sm:text-4xl">
                今天值得你关注的政策机会
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-[15px]">
                系统依据企业档案持续筛选政策、资质与赛事。先处理临近截止，再查看新匹配。
              </p>
            </div>
            <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              {[
                { label: '全部机会', value: items.length, icon: FileText },
                { label: '新匹配', value: unreadCount, icon: Award },
                { label: '14 天内截止', value: urgentCount, icon: AlarmClock },
                { label: '赛事机会', value: competitionCount, icon: Trophy },
              ].map((stat, index) => (
                <div
                  key={stat.label}
                  className={cn(
                    'flex min-h-24 items-center gap-3 p-4',
                    index % 2 === 0 && 'border-r border-border',
                    index < 2 && 'border-b border-border',
                  )}
                >
                  <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-primary">
                    <stat.icon className="size-4" />
                  </div>
                  <div>
                    <div className="font-serif text-2xl font-medium tabular-nums text-foreground">{stat.value}</div>
                    <div className="text-xs text-muted-foreground">{stat.label}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-5 rounded-xl border border-border bg-card p-2 shadow-[var(--shadow-card)]">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex gap-1 overflow-x-auto">
                {TYPE_TABS.map((t) => (
                  <button
                    key={t.value || 'all'}
                    type="button"
                    className={cn(
                      'min-h-9 shrink-0 cursor-pointer rounded-lg px-3 text-sm font-medium transition-colors',
                      typeFilter === t.value
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    )}
                    onClick={() => onTypeTab(t.value)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1 border-t border-border pt-2 lg:border-l lg:border-t-0 lg:pl-2 lg:pt-0">
                {FILTERS.map((f) => (
                  <button
                    key={f.value || 'all'}
                    type="button"
                    className={cn(
                      'min-h-8 cursor-pointer rounded-md px-2.5 text-xs font-medium transition-colors',
                      filter === f.value
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground hover:bg-muted',
                    )}
                    onClick={() => onFilter(f.value)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <div className="mb-3 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {typeFilter ? TYPE_TABS.find((tab) => tab.value === typeFilter)?.label : '全部机会'}
              </h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {renderItems.length} 条结果 · 按匹配与更新时间排序
              </p>
            </div>
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-28 w-full" />
              ))}
            </div>
          ) : inContestGrid ? (
            /* 赛事机会第一级：按参赛地区聚合的卡片，点进去看该地区比赛 */
            contestRegionGroups.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border bg-card py-20 text-center text-sm text-muted-foreground">
                <p>暂无赛事机会。</p>
                <p className="mt-2">
                  可到
                  <Button
                    variant="link"
                    className="px-1 cursor-pointer text-primary"
                    onClick={() => router.push('/sources')}
                  >
                    数据来源
                  </Button>
                  抓取赛事来源，并在
                  <Button
                    variant="link"
                    className="px-1 cursor-pointer text-primary"
                    onClick={() => router.push('/enterprise-profile')}
                  >
                    企业档案
                  </Button>
                  勾选参赛关注地区。
                </p>
              </div>
            ) : (
              <>
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-muted-foreground">按参赛地区查看，点击卡片进入该地区赛事。</p>
                  <Button
                    variant="link"
                    className="h-auto cursor-pointer gap-1 px-0 text-xs text-primary"
                    onClick={() => router.push('/sources')}
                  >
                    <DownloadCloud className="size-3.5" />
                    抓取更多赛事
                  </Button>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {contestRegionGroups.map((g) => (
                    <button
                      key={g.region}
                      type="button"
                      onClick={() => setContestRegion(g.region)}
                      className="group flex min-h-28 items-end justify-between gap-3 rounded-xl border border-border bg-card p-4 text-left shadow-[var(--shadow-card)] transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-hover)]"
                    >
                      <span className="flex min-w-0 items-center gap-3">
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                          <MapPin className="size-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-serif text-lg font-medium text-foreground">{g.region}</span>
                          <span className="text-xs text-muted-foreground">{g.count} 个可参加比赛</span>
                        </span>
                      </span>
                      <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                    </button>
                  ))}
                </div>
              </>
            )
          ) : (
            <>
              {/* 赛事下钻：返回地区网格的面包屑 */}
              {typeFilter === 'competition' && contestRegion !== null && (
                <div className="mb-3 flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="cursor-pointer h-8 gap-1 px-2 text-muted-foreground"
                    onClick={() => setContestRegion(null)}
                  >
                    <ArrowLeft className="size-4" />
                    全部地区
                  </Button>
                  <span className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
                    <MapPin className="size-4 text-primary" />
                    {contestRegion}
                  </span>
                </div>
              )}
              {renderItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border bg-card py-20 text-center text-sm text-muted-foreground">
                  <p>{typeFilter ? '该分类下暂无可申报机会。' : '暂无可申报机会。'}</p>
                  {items.length === 0 && (
                    <p className="mt-2">
                      请先完善
                      <Button
                        variant="link"
                        className="px-1 cursor-pointer text-primary"
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
                  {renderItems.map((m) => (
                <li
                  key={m.id}
                  className="group relative overflow-hidden rounded-xl border border-border bg-card p-5 pl-6 shadow-[var(--shadow-card)] transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-hover)]"
                >
                  {/* 机会类型左侧彩条：资质=翠绿、赛事=紫罗兰、政策=品牌青绿 */}
                  <span
                    className={cn(
                      'absolute left-0 top-0 h-full w-1',
                      m.type === 'qualification'
                          ? 'bg-brand-400'
                          : m.type === 'competition'
                            ? 'bg-amber-400'
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
                            ? 'border-amber-300 text-amber-700 dark:text-amber-400'
                            : 'text-muted-foreground'
                      }`}
                    >
                      {m.type === 'qualification' ? '资质' : m.type === 'competition' ? '赛事' : '政策'}
                    </Badge>
                    {/* 申报截止徽章（主线⑤；临期标红/琥珀） */}
                    <DeadlineBadge item={m} />
                    <button
                      type="button"
                      className="text-left font-semibold leading-snug text-primary line-clamp-2 cursor-pointer hover:underline"
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
                          <span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
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
            </>
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
