'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Database, ExternalLink, Globe, ShieldCheck } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { policyApi, qualificationApi, QUALIFICATION_LEVEL_LABEL } from '@/lib/api'
import type { PolicySourceItem, QualificationSourceItem } from '@/lib/api'

function formatDate(date: string | null) {
  if (!date) return '尚未抓取'
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return date
  return parsed.toLocaleDateString('zh-CN')
}

// 资质来源按级别分组展示的固定顺序
const LEVEL_ORDER = ['national', 'provincial', 'municipal', 'general']

export default function SourcesPage() {
  const [policySources, setPolicySources] = useState<PolicySourceItem[]>([])
  const [qualifications, setQualifications] = useState<QualificationSourceItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // loading 初始即 true，一次性拉取来源 + 资质目录
    Promise.all([policyApi.listSources(), qualificationApi.listCatalog()])
      .then(([sourcesRes, catalogRes]) => {
        setPolicySources(sourcesRes.items)
        setQualifications(catalogRes.items)
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : '加载数据来源失败')
      })
      .finally(() => setLoading(false))
  }, [])

  // 资质末次核对日期（目录统一核对，取首条即可）+ 全局免责声明
  const catalogReviewedAt = qualifications[0]?.last_reviewed ?? ''
  const catalogDisclaimer = qualifications[0]?.disclaimer ?? ''

  // 按级别分组，缺级别归入 general
  const groupedQualifications = useMemo(() => {
    const groups = new Map<string, QualificationSourceItem[]>()
    for (const q of qualifications) {
      const level = LEVEL_ORDER.includes(q.level) ? q.level : 'general'
      const list = groups.get(level) ?? []
      list.push(q)
      groups.set(level, list)
    }
    return LEVEL_ORDER.filter((level) => groups.has(level)).map((level) => ({
      level,
      items: groups.get(level)!,
    }))
  }, [qualifications])

  return (
    <div className="h-full overflow-hidden bg-[#f8f8f7]">
      <header className="flex min-h-16 items-center gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold text-[#202939]">数据来源</h1>
          <p className="hidden text-xs text-[#778090] sm:block">
            我们的政策与资质信息均来自政府官网与公开权威办法，以下为可溯源的来源清单。
          </p>
        </div>
      </header>

      <div className="h-[calc(100vh-4rem)] overflow-auto p-4">
        <div className="mx-auto max-w-5xl space-y-6">
          {/* ---------------- 政策数据来源 ---------------- */}
          <section className="rounded-[18px] border border-[#e5e2de] bg-white p-5 shadow-[0_10px_30px_rgba(16,24,40,.04)]">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-[#202939]">
              <Globe className="size-4" />
              政策数据来源
            </div>
            <p className="mb-4 text-xs leading-6 text-[#778090]">
              公开政策库的数据通过定期抓取以下政府门户的公开栏目入库，正文与原文链接可逐条核对。
            </p>

            {loading ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-28 w-full rounded-2xl" />
                ))}
              </div>
            ) : policySources.length === 0 ? (
              <div className="py-10 text-center text-sm text-[#778090]">暂无已登记的政策来源。</div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {policySources.map((source) => (
                  <div
                    key={source.key}
                    className="rounded-2xl border border-[#e5e2de] bg-[#fafafa] p-4 transition hover:border-[#cdd5df] hover:bg-white"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-[#202939]">{source.name}</div>
                        <Badge variant="secondary" className="mt-1 rounded-full text-[11px]">
                          {source.region}
                        </Badge>
                      </div>
                      {source.home_url && (
                        <a
                          href={source.home_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-[#287174] hover:underline"
                        >
                          <ExternalLink className="size-3.5" />
                          访问官网
                        </a>
                      )}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#667085]">
                      <span>
                        已收录 <span className="font-semibold text-[#344054]">{source.policy_count}</span> 条
                      </span>
                      <span>最近更新：{formatDate(source.last_crawled_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ---------------- 资质目录来源 ---------------- */}
          <section className="rounded-[18px] border border-[#e5e2de] bg-white p-5 shadow-[0_10px_30px_rgba(16,24,40,.04)]">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-[#202939]">
              <ShieldCheck className="size-4" />
              资质目录来源
            </div>
            <p className="mb-3 text-xs leading-6 text-[#778090]">
              资质机会目录由我们依据各级官方认定办法<span className="font-medium text-[#566070]">结构化整理</span>
              （非实时爬取）{catalogReviewedAt && <>，末次人工核对 {catalogReviewedAt}</>}。
              各资质的门槛/比例/窗口期逐年微调，请以下方政策依据的官方最新办法为准。
            </p>

            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full rounded-2xl" />
                ))}
              </div>
            ) : qualifications.length === 0 ? (
              <div className="py-10 text-center text-sm text-[#778090]">暂无资质目录数据。</div>
            ) : (
              <div className="space-y-5">
                {groupedQualifications.map((group) => (
                  <div key={group.level}>
                    <div className="mb-2 text-xs font-semibold text-[#8b92a0]">
                      {QUALIFICATION_LEVEL_LABEL[group.level] ?? group.level}
                    </div>
                    <ul className="space-y-2">
                      {group.items.map((q) => (
                        <li
                          key={q.key}
                          className="rounded-2xl border border-[#e5e2de] bg-[#fafafa] p-4"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-[#202939]">{q.name}</span>
                            {q.region && (
                              <Badge variant="outline" className="rounded-full text-[11px]">
                                {q.region}
                              </Badge>
                            )}
                          </div>
                          <dl className="mt-2 grid grid-cols-[64px_1fr] gap-x-3 gap-y-1 text-xs leading-6 text-[#566070]">
                            {q.issuer && (
                              <>
                                <dt className="text-[#8b92a0]">发证机关</dt>
                                <dd>{q.issuer}</dd>
                              </>
                            )}
                            {q.policy_basis && (
                              <>
                                <dt className="text-[#8b92a0]">政策依据</dt>
                                <dd>{q.policy_basis}</dd>
                              </>
                            )}
                          </dl>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}

                {catalogDisclaimer && (
                  <div className="rounded-2xl border border-[#f2e6c2] bg-[#fff8e8] p-3 text-xs leading-6 text-[#8a6d3b]">
                    {catalogDisclaimer}
                  </div>
                )}
              </div>
            )}
          </section>

          <p className="flex items-center justify-center gap-1.5 pb-2 text-center text-xs text-[#98a2b3]">
            <Database className="size-3.5" />
            如需新增其他地区/部门的政策来源，请联系我们评估接入。
          </p>
        </div>
      </div>
    </div>
  )
}
