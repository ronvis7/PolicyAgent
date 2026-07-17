'use client'

import { FormEvent, useCallback, useEffect, useState } from 'react'
import { ExternalLink, Globe2, Loader2, MapPin, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { contestApi } from '@/lib/api'
import type { Contest, ContestRun, ContestSource, ContestSourceSuggestion, ContestSubscription, TenantContestSource } from '@/lib/api'
import { useAuth } from '@/providers/auth-provider'

export default function ContestsPage() {
  const { role, user } = useAuth()
  const canManageSubscriptions = role === 'owner' || role === 'admin'
  const isPlatformAdmin = !!user?.is_platform_admin
  const [origin, setOrigin] = useState('')
  const [keyword, setKeyword] = useState('')
  const [region, setRegion] = useState('')
  const [source, setSource] = useState('')
  const [items, setItems] = useState<Contest[]>([])
  const [sources, setSources] = useState<ContestSource[]>([])
  const [subscriptions, setSubscriptions] = useState<ContestSubscription[]>([])
  const [tenantSources, setTenantSources] = useState<TenantContestSource[]>([])
  const [runs, setRuns] = useState<Record<string, ContestRun[]>>({})
  const [loading, setLoading] = useState(true)
  const [newKeyword, setNewKeyword] = useState('')
  const [sourceKey, setSourceKey] = useState('')
  const [sourceName, setSourceName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceRegion, setSourceRegion] = useState('全国')
  const [sourceAdapter, setSourceAdapter] = useState('cnmaker')
  const [tenantName, setTenantName] = useState('')
  const [tenantRegion, setTenantRegion] = useState('')
  const [tenantUrl, setTenantUrl] = useState('')
  const [tenantKeywords, setTenantKeywords] = useState('')
  const [tenantLinkSelector, setTenantLinkSelector] = useState('a')
  const [tenantContentSelector, setTenantContentSelector] = useState('article')
  const [tenantPresetSourceId, setTenantPresetSourceId] = useState('')
  const [suggestions, setSuggestions] = useState<ContestSourceSuggestion[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const contests = await contestApi.list({ origin, keyword, region, source, active_only: true, page_size: 50 })
      setItems(contests.items)
      const [sourceList, subscriptionList, tenantSourceList] = await Promise.allSettled([
        contestApi.sources(),
        canManageSubscriptions ? contestApi.subscriptions() : Promise.resolve({ items: [] }),
        canManageSubscriptions ? contestApi.tenantSources() : Promise.resolve({ items: [] }),
      ])
      if (sourceList.status === 'fulfilled') setSources(sourceList.value.items)
      if (subscriptionList.status === 'fulfilled') setSubscriptions(subscriptionList.value.items)
      if (tenantSourceList.status === 'fulfilled') setTenantSources(tenantSourceList.value.items)
    } catch (error) { toast.error(error instanceof Error ? error.message : '加载赛事中心失败') }
    finally { setLoading(false) }
  }, [origin, keyword, region, source, canManageSubscriptions])
  useEffect(() => { load() }, [load])

  const addSubscription = async (event: FormEvent) => {
    event.preventDefault()
    try { await contestApi.addSubscription(newKeyword); setNewKeyword(''); await load(); toast.success('已开始关注该关键词的全网赛事') }
    catch (error) { toast.error(error instanceof Error ? error.message : '添加订阅失败') }
  }
  const toggleSource = async (source: ContestSource, enabled: boolean) => {
    try { await contestApi.setSource(source.id, { enabled }); await load(); toast.success(enabled ? '官方来源已启用' : '官方来源已停用') }
    catch (error) { toast.error(error instanceof Error ? error.message : '更新来源失败') }
  }
  const addSource = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await contestApi.createSource({ key: sourceKey, name: sourceName, region: sourceRegion, home_url: sourceUrl, adapter_type: sourceAdapter, adapter_config: {}, enabled: true })
      setSourceKey(''); setSourceName(''); setSourceUrl(''); await load(); toast.success('官方赛事来源已创建')
    } catch (error) { toast.error(error instanceof Error ? error.message : '创建来源失败') }
  }
  const showRuns = async (id: string, kind: 'subscription' | 'source') => {
    try {
      const result = kind === 'subscription' ? await contestApi.subscriptionRuns(id) : await contestApi.tenantSourceRuns(id)
      setRuns((current) => ({ ...current, [id]: result.items }))
    } catch (error) { toast.error(error instanceof Error ? error.message : '加载运行记录失败') }
  }
  const addTenantSource = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await contestApi.createTenantSource({ name: tenantName, region: tenantRegion, list_url: tenantUrl, title_keywords: tenantKeywords, link_selector: tenantLinkSelector, content_selector: tenantContentSelector, preset_source_id: tenantPresetSourceId || null })
      setTenantName(''); setTenantRegion(''); setTenantUrl(''); setTenantKeywords(''); setTenantPresetSourceId(''); await load(); toast.success('已创建，请先预检后启用')
    } catch (error) { toast.error(error instanceof Error ? error.message : '创建企业来源失败') }
  }
  const suggestTenantSource = async () => {
    if (!tenantRegion.trim()) { toast.error('请先输入地区'); return }
    try {
      const result = await contestApi.suggestTenantSources(tenantRegion)
      setSuggestions(result.items)
      if (!result.items.length) toast.message('暂未找到可自动配置的公开门户，可改用高级配置')
    } catch (error) { toast.error(error instanceof Error ? error.message : '智能查找门户失败') }
  }
  const applySuggestion = (item: ContestSourceSuggestion) => {
    setTenantPresetSourceId(''); setTenantName(item.name); setTenantRegion(item.region); setTenantUrl(item.list_url)
    setTenantKeywords(item.title_keywords); setTenantLinkSelector(item.link_selector); setTenantContentSelector(item.content_selector)
    toast.success('已自动填入，请点击创建后执行预检')
  }

  return <div className="flex h-full flex-col bg-background">
    <header className="flex min-h-16 items-center gap-3 border-b border-border px-4 py-3"><SidebarTrigger className="cursor-pointer rounded-lg hover:bg-card" /><div><h1 className="font-serif text-xl font-semibold text-foreground">赛事中心</h1><p className="text-xs text-muted-foreground">全部收录赛事；工作台只展示为企业筛选后的推荐。</p></div></header>
    <main className="flex-1 overflow-auto p-4 sm:p-6"><div className="mx-auto max-w-5xl space-y-5">
      <section className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]"><div className="flex flex-wrap gap-1">{[['', '全部赛事'], ['official', '官方来源'], ['web', '全网发现']].map(([value, label]) => <Button key={value} size="sm" variant={origin === value ? 'default' : 'ghost'} onClick={() => setOrigin(value)}>{label}</Button>)}</div><div className="mt-2 grid gap-2 sm:grid-cols-[1fr_150px_180px_auto]"><Input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索赛事标题或正文" className="h-9" /><Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="地区" className="h-9" /><select value={source} onChange={(e) => setSource(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm"><option value="">全部来源</option>{sources.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}</select><Button size="sm" variant="outline" onClick={load}><Search className="size-4" />查询</Button></div></section>
      {canManageSubscriptions && <section className="rounded-xl border border-border bg-card p-4"><div className="mb-2 flex items-center gap-2 font-medium text-foreground"><Globe2 className="size-4 text-primary" />全网赛事关键词订阅</div><form onSubmit={addSubscription} className="flex gap-2"><Input value={newKeyword} onChange={(e) => setNewKeyword(e.target.value)} placeholder="例如：人工智能、专精特新、机器人" /><Button type="submit">添加</Button></form><div className="mt-3 flex flex-wrap gap-2">{subscriptions.map((sub) => <Badge key={sub.id} variant={sub.enabled ? 'secondary' : 'outline'} className="gap-1.5 py-1"><Switch checked={sub.enabled} onCheckedChange={(enabled) => contestApi.setSubscription(sub.id, enabled).then(load)} />{sub.keyword}<button type="button" className="ml-1 text-muted-foreground" onClick={() => contestApi.deleteSubscription(sub.id).then(load)}>×</button></Badge>)}</div></section>}
      {canManageSubscriptions && <section className="rounded-xl border border-border bg-card p-4"><div className="mb-2 font-medium text-foreground">全网发现运行记录</div><div className="space-y-2">{subscriptions.map((sub) => <div key={sub.id} className="rounded-lg border border-border p-3"><div className="flex items-center justify-between gap-2"><span>{sub.keyword}</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={!sub.enabled} onClick={() => contestApi.discoverSubscription(sub.id).then(() => { toast.success('已开始搜索'); showRuns(sub.id, 'subscription') }).catch((e) => toast.error(e.message))}>立即搜索</Button><Button size="sm" variant="ghost" onClick={() => showRuns(sub.id, 'subscription')}>记录</Button></div></div>{runs[sub.id]?.map((run) => <p key={run.id} className="mt-1 text-xs text-muted-foreground">{run.status} · 检索 {run.searched_count} · 有效 {run.valid_count} · 入库 {run.stored_count}{run.error_message ? ` · ${run.error_message}` : ''}</p>)}</div>)}</div></section>}
      {canManageSubscriptions && <section className="rounded-xl border border-border bg-card p-4"><div className="mb-2 font-medium text-foreground">我的赛事来源</div><p className="mb-3 text-xs text-muted-foreground">优先按地区选择已验证的官方门户；没有预设时，输入地区后让 Agent 搜索公开门户并自动填表，最后仍需预检确认。</p><form onSubmit={addTenantSource} className="grid gap-2 sm:grid-cols-2"><select value={tenantPresetSourceId} onChange={(e) => { const selected = sources.find((item) => item.id === e.target.value); setTenantPresetSourceId(e.target.value); if (selected) { setTenantName(selected.name); setTenantRegion(selected.region) } }} className="h-9 rounded-md border border-input bg-background px-3 text-sm"><option value="">选择关注地区的官方来源（或使用智能查找）</option>{sources.map((item) => <option key={item.id} value={item.id}>{item.region} · {item.name}</option>)}</select><Input value={tenantName} onChange={(e) => setTenantName(e.target.value)} placeholder="来源名称（选预设后自动填充）" /><div className="flex gap-2"><Input value={tenantRegion} onChange={(e) => setTenantRegion(e.target.value)} placeholder="地区" /><Button type="button" variant="outline" onClick={suggestTenantSource}>智能查找</Button></div><Input value={tenantUrl} disabled={!!tenantPresetSourceId} onChange={(e) => setTenantUrl(e.target.value)} placeholder="高级：公开列表页 URL" /><Input value={tenantKeywords} disabled={!!tenantPresetSourceId} onChange={(e) => setTenantKeywords(e.target.value)} placeholder="高级：标题关键词（可选）" /><Input value={tenantLinkSelector} disabled={!!tenantPresetSourceId} onChange={(e) => setTenantLinkSelector(e.target.value)} placeholder="高级：列表链接 CSS" /><Input value={tenantContentSelector} disabled={!!tenantPresetSourceId} onChange={(e) => setTenantContentSelector(e.target.value)} placeholder="高级：正文 CSS" /><Button type="submit" className="sm:col-span-2">添加我的地区来源</Button></form>{suggestions.length > 0 && <div className="mt-3 space-y-2">{suggestions.map((item) => <button key={item.list_url} type="button" className="block w-full rounded-lg border border-border p-3 text-left text-sm hover:bg-muted" onClick={() => applySuggestion(item)}><span className="font-medium">{item.name}</span><span className="ml-2 text-xs text-muted-foreground">{item.list_url}</span><p className="mt-1 text-xs text-muted-foreground">{item.reason}</p></button>)}</div>}<div className="mt-4 grid gap-3 sm:grid-cols-2">{tenantSources.map((item) => <article key={item.id} className="rounded-lg border border-border p-3"><div className="flex items-start justify-between gap-2"><div><p className="font-medium">{item.name}</p><p className="text-xs text-muted-foreground">{item.region} · {item.preset_source_id ? '官方地区预设' : '自定义门户'} · {item.preflight_at ? '已预检' : '未预检'}</p></div><Switch checked={item.enabled} onCheckedChange={(enabled) => contestApi.setTenantSource(item.id, { enabled }).then(load).catch((e) => toast.error(e.message))} /></div><div className="mt-3 flex gap-2"><Button size="sm" variant="outline" onClick={() => contestApi.preflightTenantSource(item.id).then((result) => { toast.success(`预检成功：${result.sample_count} 条样本`); load() }).catch((e) => toast.error(e.message))}>预检</Button><Button size="sm" disabled={!item.enabled} onClick={() => contestApi.ingestTenantSource(item.id).then(() => { toast.success('已开始抓取'); showRuns(item.id, 'source') }).catch((e) => toast.error(e.message))}>抓取</Button><Button size="sm" variant="ghost" onClick={() => showRuns(item.id, 'source')}>记录</Button></div>{runs[item.id]?.map((run) => <p key={run.id} className="mt-1 text-xs text-muted-foreground">{run.status} · 抓取 {run.searched_count} · 入库 {run.stored_count}{run.error_message ? ` · ${run.error_message}` : ''}</p>)}</article>)}</div></section>}
      {isPlatformAdmin && <section className="rounded-xl border border-border bg-card p-4"><div className="mb-2 flex items-center gap-2 font-medium text-foreground"><ShieldCheck className="size-4 text-primary" />添加可信官方来源</div><p className="mb-3 text-xs text-muted-foreground">仅支持已验证的门户模板；创建后可先预检，再手动抓取。</p><form onSubmit={addSource} className="grid gap-2 sm:grid-cols-5"><Input value={sourceKey} onChange={(e) => setSourceKey(e.target.value)} placeholder="来源 key" /><Input value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="显示名称" /><Input value={sourceRegion} onChange={(e) => setSourceRegion(e.target.value)} placeholder="地区" /><Input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="门户 URL" /><select value={sourceAdapter} onChange={(e) => setSourceAdapter(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm"><option value="cnmaker">创客中国</option><option value="wnd">无锡门户</option><option value="gxt">江苏工信</option><option value="cq">重庆门户</option></select><Button type="submit" className="sm:col-span-5">创建官方来源</Button></form></section>}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{sources.map((source) => <article key={source.id} className="rounded-xl border border-border bg-card p-4"><div className="flex items-start justify-between gap-2"><div><div className="flex items-center gap-1.5 text-sm font-medium text-foreground"><ShieldCheck className="size-4 text-primary" />{source.name}</div><p className="mt-1 text-xs text-muted-foreground">{source.region} · {source.adapter_type}</p></div>{isPlatformAdmin && <Switch checked={source.enabled} onCheckedChange={(enabled) => toggleSource(source, enabled)} />}</div><a href={source.home_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">访问门户 <ExternalLink className="size-3" /></a>{isPlatformAdmin && <div className="mt-3 flex gap-2"><Button size="sm" variant="outline" onClick={() => contestApi.preflightSource(source.id).then((r) => toast.success(`预检成功：${r.sample_count} 条样本`)).catch((e) => toast.error(e.message))}>预检</Button><Button size="sm" onClick={() => contestApi.ingestSource(source.id).then(() => toast.success('已开始抓取')).catch((e) => toast.error(e.message))}>抓取</Button></div>}</article>)}</section>
      {loading ? <div className="flex justify-center py-16"><Loader2 className="animate-spin text-primary" /></div> : items.length === 0 ? <div className="rounded-xl border border-dashed border-border py-16 text-center text-sm text-muted-foreground">暂无符合条件的赛事。官方来源会每日抓取；企业管理员可添加关键词订阅全网发现。</div> : <section className="space-y-3">{items.map((item) => <article key={item.id} className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"><div className="mb-2 flex flex-wrap items-center gap-2"><Badge variant={item.origin === 'official' ? 'secondary' : 'outline'}>{item.origin === 'official' ? '官方来源' : '全网发现'}</Badge><Badge variant="outline"><MapPin className="mr-1 size-3" />{item.region || '全国'}</Badge>{item.apply_deadline && <Badge variant="outline">报名截止 {item.apply_deadline}</Badge>}</div><a href={item.source_url} target="_blank" rel="noreferrer" className="text-base font-semibold text-primary hover:underline">{item.title}</a><p className="mt-2 text-xs text-muted-foreground">来源：{item.source_name || item.source}</p></article>)}</section>}
    </div></main>
  </div>
}
