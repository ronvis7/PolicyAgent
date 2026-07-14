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
import type { Contest, ContestSource, ContestSubscription } from '@/lib/api'
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
  const [loading, setLoading] = useState(true)
  const [newKeyword, setNewKeyword] = useState('')
  const [sourceKey, setSourceKey] = useState('')
  const [sourceName, setSourceName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceAdapter, setSourceAdapter] = useState('cnmaker')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [contests, sourceList, subscriptionList] = await Promise.all([
        contestApi.list({ origin, keyword, region, source, active_only: true, page_size: 50 }), contestApi.sources(),
        canManageSubscriptions ? contestApi.subscriptions() : Promise.resolve({ items: [] }),
      ])
      setItems(contests.items); setSources(sourceList.items); setSubscriptions(subscriptionList.items)
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
      await contestApi.createSource({ key: sourceKey, name: sourceName, region: '全国', home_url: sourceUrl, adapter_type: sourceAdapter, adapter_config: {}, enabled: true })
      setSourceKey(''); setSourceName(''); setSourceUrl(''); await load(); toast.success('官方赛事来源已创建')
    } catch (error) { toast.error(error instanceof Error ? error.message : '创建来源失败') }
  }

  return <div className="flex h-full flex-col bg-background">
    <header className="flex min-h-16 items-center gap-3 border-b border-border px-4 py-3"><SidebarTrigger className="cursor-pointer rounded-lg hover:bg-card" /><div><h1 className="font-serif text-xl font-semibold text-foreground">赛事中心</h1><p className="text-xs text-muted-foreground">全部收录赛事；工作台只展示为企业筛选后的推荐。</p></div></header>
    <main className="flex-1 overflow-auto p-4 sm:p-6"><div className="mx-auto max-w-5xl space-y-5">
      <section className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]"><div className="flex flex-wrap gap-1">{[['', '全部赛事'], ['official', '官方来源'], ['web', '全网发现']].map(([value, label]) => <Button key={value} size="sm" variant={origin === value ? 'default' : 'ghost'} onClick={() => setOrigin(value)}>{label}</Button>)}</div><div className="mt-2 grid gap-2 sm:grid-cols-[1fr_150px_180px_auto]"><Input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索赛事标题或正文" className="h-9" /><Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="地区" className="h-9" /><select value={source} onChange={(e) => setSource(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm"><option value="">全部来源</option>{sources.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}</select><Button size="sm" variant="outline" onClick={load}><Search className="size-4" />查询</Button></div></section>
      {canManageSubscriptions && <section className="rounded-xl border border-border bg-card p-4"><div className="mb-2 flex items-center gap-2 font-medium text-foreground"><Globe2 className="size-4 text-primary" />全网赛事关键词订阅</div><form onSubmit={addSubscription} className="flex gap-2"><Input value={newKeyword} onChange={(e) => setNewKeyword(e.target.value)} placeholder="例如：人工智能、专精特新、机器人" /><Button type="submit">添加</Button></form><div className="mt-3 flex flex-wrap gap-2">{subscriptions.map((sub) => <Badge key={sub.id} variant={sub.enabled ? 'secondary' : 'outline'} className="gap-1.5 py-1"><Switch checked={sub.enabled} onCheckedChange={(enabled) => contestApi.setSubscription(sub.id, enabled).then(load)} />{sub.keyword}<button type="button" className="ml-1 text-muted-foreground" onClick={() => contestApi.deleteSubscription(sub.id).then(load)}>×</button></Badge>)}</div></section>}
      {isPlatformAdmin && <section className="rounded-xl border border-border bg-card p-4"><div className="mb-2 flex items-center gap-2 font-medium text-foreground"><ShieldCheck className="size-4 text-primary" />添加可信官方来源</div><p className="mb-3 text-xs text-muted-foreground">仅支持已验证的门户模板；创建后可先预检，再手动抓取。</p><form onSubmit={addSource} className="grid gap-2 sm:grid-cols-4"><Input value={sourceKey} onChange={(e) => setSourceKey(e.target.value)} placeholder="来源 key" /><Input value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="显示名称" /><Input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="门户 URL" /><select value={sourceAdapter} onChange={(e) => setSourceAdapter(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm"><option value="cnmaker">创客中国</option><option value="wnd">无锡门户</option><option value="gxt">江苏工信</option></select><Button type="submit" className="sm:col-span-4">创建官方来源</Button></form></section>}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{sources.map((source) => <article key={source.id} className="rounded-xl border border-border bg-card p-4"><div className="flex items-start justify-between gap-2"><div><div className="flex items-center gap-1.5 text-sm font-medium text-foreground"><ShieldCheck className="size-4 text-primary" />{source.name}</div><p className="mt-1 text-xs text-muted-foreground">{source.region} · {source.adapter_type}</p></div>{isPlatformAdmin && <Switch checked={source.enabled} onCheckedChange={(enabled) => toggleSource(source, enabled)} />}</div><a href={source.home_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">访问门户 <ExternalLink className="size-3" /></a>{isPlatformAdmin && <div className="mt-3 flex gap-2"><Button size="sm" variant="outline" onClick={() => contestApi.preflightSource(source.id).then((r) => toast.success(`预检成功：${r.sample_count} 条样本`)).catch((e) => toast.error(e.message))}>预检</Button><Button size="sm" onClick={() => contestApi.ingestSource(source.id).then(() => toast.success('已开始抓取')).catch((e) => toast.error(e.message))}>抓取</Button></div>}</article>)}</section>
      {loading ? <div className="flex justify-center py-16"><Loader2 className="animate-spin text-primary" /></div> : items.length === 0 ? <div className="rounded-xl border border-dashed border-border py-16 text-center text-sm text-muted-foreground">暂无符合条件的赛事。官方来源会每日抓取；企业管理员可添加关键词订阅全网发现。</div> : <section className="space-y-3">{items.map((item) => <article key={item.id} className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"><div className="mb-2 flex flex-wrap items-center gap-2"><Badge variant={item.origin === 'official' ? 'secondary' : 'outline'}>{item.origin === 'official' ? '官方来源' : '全网发现'}</Badge><Badge variant="outline"><MapPin className="mr-1 size-3" />{item.region || '全国'}</Badge>{item.apply_deadline && <Badge variant="outline">报名截止 {item.apply_deadline}</Badge>}</div><a href={item.source_url} target="_blank" rel="noreferrer" className="text-base font-semibold text-primary hover:underline">{item.title}</a><p className="mt-2 text-xs text-muted-foreground">来源：{item.source_name || item.source}</p></article>)}</section>}
    </div></main>
  </div>
}
