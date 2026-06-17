'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  Bot,
  CheckSquare2,
  ChevronLeft,
  ChevronRight,
  DownloadCloud,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCcw,
  Search,
  Sparkles,
} from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { policyApi } from '@/lib/api'
import type { PolicyDetail, PolicyListItem, PolicySourceItem } from '@/lib/api'
import { useAuth } from '@/providers/auth-provider'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 20
// 抓取是后端 fire-and-forget 后台任务(约 1-2 分钟)，端点立即返回。
// 前端在此窗口内保持"抓取中"态 + 横幅提示，窗口结束自动刷新列表，避免用户误以为没工作。
const INGEST_WINDOW_MS = 90_000

function formatDate(date: string | null) {
  if (!date) return '未标注日期'
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return date
  return parsed.toLocaleDateString('zh-CN')
}

function excerpt(text: string, length = 180) {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean) return '该政策正文暂未入库，请查看原文链接确认完整内容。'
  return clean.length > length ? `${clean.slice(0, length)}...` : clean
}

function statusClass(status: string) {
  if (status.includes('有效') || status.includes('现行')) return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (status.includes('失效') || status.includes('废止')) return 'border-rose-200 bg-rose-50 text-rose-700'
  return 'border-[#e5e2de] bg-white text-[#667085]'
}

export default function PoliciesPage() {
  const { role } = useAuth()
  const canIngest = role === 'owner' || role === 'admin'

  const [items, setItems] = useState<PolicyListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [search, setSearch] = useState('')
  const [region, setRegion] = useState('')
  const [issuer, setIssuer] = useState('')
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  const [ingestingSource, setIngestingSource] = useState<string | null>(null)
  const ingestTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [sources, setSources] = useState<PolicySourceItem[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const [detail, setDetail] = useState<PolicyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const selectedItem = detail ?? items[0] ?? null
  const selectedCount = selectedIds.length

  const regionOptions = useMemo(() => Array.from(new Set(sources.map((s) => s.region))), [sources])
  const issuerOptions = useMemo(
    () => Array.from(new Set(items.map((item) => item.issuer).filter(Boolean))).slice(0, 12),
    [items],
  )

  const fetchList = useCallback(() => {
    setLoading(true)
    policyApi
      .list({ page, page_size: PAGE_SIZE, keyword: search, region, issuer })
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
        setSelectedIds([])
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : '获取政策列表失败')
      })
      .finally(() => setLoading(false))
  }, [page, search, region, issuer])

  useEffect(() => {
    queueMicrotask(fetchList)
  }, [fetchList])

  useEffect(() => {
    policyApi
      .listSources()
      .then((res) => setSources(res.items))
      .catch(() => setSources([]))
  }, [])

  const submitSearch = () => {
    setPage(1)
    setSearch(keyword.trim())
  }

  // 组件卸载时清掉抓取窗口定时器，避免卸载后 setState
  useEffect(() => () => {
    if (ingestTimerRef.current) clearTimeout(ingestTimerRef.current)
  }, [])

  const handleIngest = async (sourceKey: string, sourceName: string) => {
    if (ingesting) return
    setIngesting(true)
    setIngestingSource(sourceName)
    try {
      const res = await policyApi.ingest(sourceKey, 3)
      toast.success(`已开始后台抓取「${sourceName}」（最多 ${res.max_pages} 页），约 1-2 分钟，完成后自动刷新`)
      if (ingestTimerRef.current) clearTimeout(ingestTimerRef.current)
      ingestTimerRef.current = setTimeout(() => {
        ingestTimerRef.current = null
        setIngesting(false)
        setIngestingSource(null)
        fetchList()
        toast.success(`「${sourceName}」抓取窗口结束，已刷新列表`)
      }, INGEST_WINDOW_MS)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '触发抓取失败')
      setIngesting(false)
      setIngestingSource(null)
    }
  }

  const openDetail = async (id: string) => {
    setDetailLoading(true)
    try {
      setDetail(await policyApi.get(id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '获取政策详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]))
  }

  const allCurrentSelected = items.length > 0 && items.every((item) => selectedIds.includes(item.id))

  return (
    <div className="h-full overflow-hidden bg-[#f8f8f7]">
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-[#202939]">公开政策库</h1>
            <p className="hidden text-xs text-[#778090] sm:block">搜索、筛选和审阅已入库的公开政策，结果来自现有政策库接口。</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canIngest && sources.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild disabled={ingesting}>
                <Button variant="outline" className="cursor-pointer rounded-xl bg-white" title="选择来源后台抓取最新政策入库">
                  {ingesting ? <Loader2 className="size-4 animate-spin" /> : <DownloadCloud className="size-4" />}
                  {ingesting ? '抓取中…' : '抓取政策'}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-60">
                <DropdownMenuLabel className="text-xs text-muted-foreground">选择抓取来源</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {sources.map((source) => (
                  <DropdownMenuItem key={source.key} className="cursor-pointer" onSelect={() => handleIngest(source.key, source.name)}>
                    <span className="truncate">{source.name}</span>
                    <span className="ml-auto text-[10px] text-muted-foreground">{source.region}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button variant="outline" className="cursor-pointer rounded-xl bg-white" onClick={fetchList} disabled={loading}>
            <RefreshCcw className={cn('size-4', loading && 'animate-spin')} />
            刷新
          </Button>
        </div>
      </header>

      {ingestingSource && (
        <div className="flex items-center gap-2 border-b border-[#f2e6c2] bg-[#fff8e8] px-4 py-2 text-sm text-[#8a6d3b]">
          <Loader2 className="size-4 shrink-0 animate-spin" />
          正在后台抓取「{ingestingSource}」最新政策，约 1-2 分钟，完成后会自动刷新列表（也可随时点右上角「刷新」）。
        </div>
      )}

      <div className="grid h-[calc(100vh-4rem)] grid-cols-1 gap-4 overflow-hidden p-4 xl:grid-cols-[minmax(0,1fr)_390px]">
        <main className="min-w-0 overflow-auto pr-0 xl:pr-1">
          <section className="mb-4 rounded-[18px] border border-[#e5e2de] bg-white p-4 shadow-[0_10px_30px_rgba(16,24,40,.04)]">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-[#202939]">
                  <Sparkles className="size-4" />
                  政策检索
                </div>
                <p className="mt-1 text-xs text-[#778090]">地区、发布部门和关键词会直接传给公开政策库列表接口。</p>
              </div>
              <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
                {regionOptions.length > 0 && (
                  <select
                    value={region}
                    onChange={(event) => { setPage(1); setRegion(event.target.value) }}
                    className="h-10 rounded-xl border border-[#e5e2de] bg-white px-3 text-sm text-[#344054] outline-none"
                    title="按地区筛选"
                  >
                    <option value="">全部地区</option>
                    {regionOptions.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                )}
                <select
                  value={issuer}
                  onChange={(event) => { setPage(1); setIssuer(event.target.value) }}
                  className="h-10 rounded-xl border border-[#e5e2de] bg-white px-3 text-sm text-[#344054] outline-none"
                  title="按发布部门筛选"
                >
                  <option value="">全部部门</option>
                  {issuerOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <div className="flex min-w-[260px] flex-1 items-center gap-2 rounded-xl border border-[#e5e2de] bg-[#fafafa] px-3">
                  <Search className="size-4 text-[#98a2b3]" />
                  <Input
                    value={keyword}
                    placeholder="搜索政策标题、文号或主题..."
                    className="h-10 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
                    onChange={(event) => setKeyword(event.target.value)}
                    onKeyDown={(event) => event.key === 'Enter' && submitSearch()}
                  />
                </div>
                <Button className="cursor-pointer rounded-xl" onClick={submitSearch}>
                  搜索
                </Button>
              </div>
            </div>
          </section>

          <section className="mb-4 rounded-[18px] border border-[#e5e2de] bg-[#eef8f8] p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-3">
                <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-white text-[#2f3747]">
                  <Bot className="size-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-[#202939]">结果概览</div>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-[#566070]">
                    当前条件下共找到 {total} 条政策。优先查看状态、地区、发文机关和正文证据；需要进入企业适配判断时，请回到工作台重新匹配。
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="rounded-full bg-white">地区：{region || '全部'}</Badge>
                <Badge variant="outline" className="rounded-full bg-white">部门：{issuer || '全部'}</Badge>
                <Badge variant="outline" className="rounded-full bg-white">已选：{selectedCount}</Badge>
              </div>
            </div>
          </section>

          <section className="rounded-[18px] border border-[#e5e2de] bg-white p-4 shadow-[0_10px_30px_rgba(16,24,40,.04)]">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-[#566070]">
                <input
                  type="checkbox"
                  checked={allCurrentSelected}
                  onChange={() => setSelectedIds(allCurrentSelected ? [] : items.map((item) => item.id))}
                  className="size-4 rounded border-[#d9d6d2]"
                />
                选择本页
              </label>
              <div className="flex items-center gap-2 text-sm text-[#778090]">
                <CheckSquare2 className="size-4" />
                {selectedCount > 0 ? `已选择 ${selectedCount} 条，可用于后续报告草稿整理` : '选择政策后可批量整理材料'}
              </div>
            </div>

            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="h-32 w-full rounded-2xl" />
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="py-20 text-center text-sm text-[#778090]">
                暂无政策数据{search ? `（无匹配「${search}」的结果）` : ''}。
              </div>
            ) : (
              <ul className="space-y-3">
                {items.map((policy) => (
                  <li
                    key={policy.id}
                    className={cn(
                      'rounded-2xl border border-[#e5e2de] bg-[#fafafa] p-4 transition hover:border-[#cdd5df] hover:bg-white',
                      detail?.id === policy.id && 'border-[#2f3747] bg-white shadow-sm',
                    )}
                  >
                    <div className="flex gap-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(policy.id)}
                        onChange={() => toggleSelected(policy.id)}
                        className="mt-1 size-4 shrink-0 rounded border-[#d9d6d2]"
                        aria-label={`选择 ${policy.title}`}
                      />
                      <FileText className="mt-0.5 size-5 shrink-0 text-[#667085]" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-[#778090]">
                          <span>{policy.source || '公开来源'}</span>
                          {policy.region && <span>· {policy.region}</span>}
                          {policy.issuer && <span>· {policy.issuer}</span>}
                        </div>
                        <button
                          type="button"
                          className="mt-2 text-left text-lg font-semibold leading-snug text-[#287174] hover:underline"
                          onClick={() => openDetail(policy.id)}
                        >
                          {policy.title}
                        </button>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-[#667085]">
                          <Badge variant="outline" className={cn('rounded-full', statusClass(policy.status || ''))}>
                            {policy.status || '未标注状态'}
                          </Badge>
                          <span>{formatDate(policy.publish_date)}</span>
                          {policy.doc_number && <span>文号：{policy.doc_number}</span>}
                          {policy.index_number && <span>索引号：{policy.index_number}</span>}
                        </div>
                      </div>
                      <Button variant="ghost" className="shrink-0 cursor-pointer rounded-xl" onClick={() => openDetail(policy.id)}>
                        查看详情
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {!loading && total > 0 && (
              <div className="mt-6 flex items-center justify-center gap-4 text-sm">
                <Button variant="outline" size="sm" className="cursor-pointer rounded-xl bg-white" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  <ChevronLeft className="size-4" />
                  上一页
                </Button>
                <span className="text-[#778090]">{page} / {totalPages}</span>
                <Button variant="outline" size="sm" className="cursor-pointer rounded-xl bg-white" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
                  下一页
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            )}
          </section>
        </main>

        <aside className="hidden min-h-0 flex-col overflow-hidden rounded-[20px] border border-[#e5e2de] bg-white shadow-[0_10px_30px_rgba(16,24,40,.05)] xl:flex">
          <div className="border-b border-[#e5e2de] bg-[#9bd6d8] px-4 py-3">
            <div className="flex items-center gap-2 text-base font-semibold text-[#202939]">
              <Sparkles className="size-5" />
              政策助手
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            {detailLoading ? (
              <div className="flex items-center justify-center py-20 text-[#778090]">
                <Loader2 className="size-5 animate-spin" />
              </div>
            ) : selectedItem ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-[#e5e2de] bg-[#fafafa] p-4">
                  <div className="mb-2 text-xs font-semibold text-[#778090]">当前审阅</div>
                  <h2 className="text-base font-semibold leading-relaxed text-[#202939]">{selectedItem.title}</h2>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {'status' in selectedItem && selectedItem.status && (
                      <Badge variant="outline" className={cn('rounded-full', statusClass(selectedItem.status))}>
                        {selectedItem.status}
                      </Badge>
                    )}
                    {'region' in selectedItem && selectedItem.region && <Badge variant="secondary" className="rounded-full">{selectedItem.region}</Badge>}
                  </div>
                </div>

                <div className="rounded-2xl border border-[#e5e2de] p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-[#202939]">
                    <Bot className="size-4" />
                    阅读摘要
                  </div>
                  <p className="text-sm leading-7 text-[#566070]">
                    {detail ? excerpt(detail.body_text) : '点击左侧政策后，这里会展示正文摘要和证据入口。'}
                  </p>
                </div>

                {detail && (
                  <>
                    <div className="rounded-2xl border border-[#e5e2de] p-4">
                      <div className="mb-2 text-sm font-semibold text-[#202939]">政策元数据</div>
                      <dl className="grid grid-cols-[72px_1fr] gap-2 text-sm">
                        <dt className="text-[#8b92a0]">发文机关</dt>
                        <dd className="font-medium text-[#344054]">{detail.issuer || '-'}</dd>
                        <dt className="text-[#8b92a0]">发布日期</dt>
                        <dd className="font-medium text-[#344054]">{formatDate(detail.publish_date)}</dd>
                        <dt className="text-[#8b92a0]">文号</dt>
                        <dd className="font-medium text-[#344054]">{detail.doc_number || '-'}</dd>
                        <dt className="text-[#8b92a0]">入库时间</dt>
                        <dd className="font-medium text-[#344054]">{formatDate(detail.crawled_at)}</dd>
                      </dl>
                    </div>
                    <div className="rounded-2xl border border-[#e5e2de] p-4">
                      <div className="mb-2 text-sm font-semibold text-[#202939]">正文预览</div>
                      <div className="max-h-72 overflow-auto whitespace-pre-wrap text-sm leading-7 text-[#566070]">
                        {detail.body_text || '暂无正文，请查看原文链接。'}
                      </div>
                    </div>
                    {detail.source_url && (
                      <a
                        href={detail.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm font-medium text-[#287174] hover:underline"
                      >
                        <ExternalLink className="size-4" />
                        查看原文
                      </a>
                    )}
                  </>
                )}
              </div>
            ) : (
              <div className="py-20 text-center text-sm text-[#778090]">暂无可审阅政策。</div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
