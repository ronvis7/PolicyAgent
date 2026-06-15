'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ChevronLeft, ChevronRight, DownloadCloud, ExternalLink, Loader2, ScrollText, Search } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

const PAGE_SIZE = 20

/** 公开政策库浏览页：全局共享层，所有登录用户可分页检索浏览政策。 */
export default function PoliciesPage() {
  const { role } = useAuth()
  const canIngest = role === 'owner' || role === 'admin'

  const [items, setItems] = useState<PolicyListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [search, setSearch] = useState('') // 已提交的查询词
  const [region, setRegion] = useState('') // 地区筛选（''=全部）
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  const [sources, setSources] = useState<PolicySourceItem[]>([])

  const [detail, setDetail] = useState<PolicyDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const fetchList = useCallback(() => {
    setLoading(true)
    policyApi
      .list({ page, page_size: PAGE_SIZE, keyword: search, region })
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : '获取政策列表失败')
      })
      .finally(() => setLoading(false))
  }, [page, search, region])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  // 加载可抓取的政策来源（地区/门户），供来源选择器与地区筛选
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

  const handleIngest = async (sourceKey: string, sourceName: string) => {
    setIngesting(true)
    try {
      const res = await policyApi.ingest(sourceKey, 3)
      toast.success(`已开始抓取「${sourceName}」（最多 ${res.max_pages} 页），约 1-2 分钟后点刷新查看`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '触发抓取失败')
    } finally {
      setIngesting(false)
    }
  }

  // 地区筛选项：来自已登记来源的地区（去重）
  const regionOptions = Array.from(new Set(sources.map((s) => s.region)))

  const openDetail = async (id: string) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      const d = await policyApi.get(id)
      setDetail(d)
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
          <h1 className="text-base font-semibold">公开政策库</h1>
        </div>
        <div className="flex items-center gap-2">
          {/* 地区筛选 */}
          {regionOptions.length > 0 && (
            <select
              value={region}
              onChange={(e) => { setPage(1); setRegion(e.target.value) }}
              className="h-9 rounded-md border bg-background px-2 text-sm cursor-pointer"
              title="按地区筛选"
            >
              <option value="">全部地区</option>
              {regionOptions.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          )}
          <Input
            value={keyword}
            placeholder="搜索政策标题…"
            className="w-40 sm:w-56"
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submitSearch()}
          />
          <Button variant="outline" className="cursor-pointer" onClick={submitSearch}>
            <Search className="size-4" />
            搜索
          </Button>
          {canIngest && sources.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild disabled={ingesting}>
                <Button variant="outline" className="cursor-pointer" title="选择来源后台抓取最新政策入库">
                  {ingesting ? <Loader2 className="size-4 animate-spin" /> : <DownloadCloud className="size-4" />}
                  抓取政策
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-56">
                <DropdownMenuLabel className="text-xs text-muted-foreground">选择抓取来源</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {sources.map((s) => (
                  <DropdownMenuItem
                    key={s.key}
                    className="cursor-pointer"
                    onSelect={() => handleIngest(s.key, s.name)}
                  >
                    <span className="truncate">{s.name}</span>
                    <span className="ml-auto text-[10px] text-muted-foreground">{s.region}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button variant="outline" className="cursor-pointer" onClick={fetchList} disabled={loading}>
            刷新
          </Button>
        </div>
      </header>

      {/* 列表 */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-[900px] mx-auto">
          <div className="mb-4 flex items-center gap-2 text-muted-foreground">
            <ScrollText className="size-5" />
            <span className="text-sm">
              {region ? `${region}权威政策` : '各地区权威政策'}（公开共享）。共 {total} 条，点击查看详情。
            </span>
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-20 text-center text-muted-foreground text-sm">
              暂无政策数据{search ? `（无匹配「${search}」的结果）` : ''}。
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((p) => (
                <li
                  key={p.id}
                  className="rounded-lg border p-4 cursor-pointer hover:border-primary/50 hover:bg-accent/40 transition-colors"
                  onClick={() => openDetail(p.id)}
                >
                  <div className="font-medium mb-1 line-clamp-2">{p.title}</div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {p.publish_date && <span>{p.publish_date}</span>}
                    {p.issuer && <Badge variant="secondary">{p.issuer}</Badge>}
                    {p.status && <Badge variant="outline">{p.status}</Badge>}
                    {p.doc_number && <span>{p.doc_number}</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {/* 分页 */}
          {!loading && total > 0 && (
            <div className="mt-6 flex items-center justify-center gap-4 text-sm">
              <Button
                variant="outline"
                size="sm"
                className="cursor-pointer"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="size-4" />
                上一页
              </Button>
              <span className="text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="cursor-pointer"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                下一页
                <ChevronRight className="size-4" />
              </Button>
            </div>
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
