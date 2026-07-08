'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { toast } from 'sonner'
import {
  Award,
  Building2,
  Loader2,
  MapPin,
  Pencil,
  Save,
  Sparkles,
  Tags,
  TrendingUp,
  Trophy,
  X,
} from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import { policyApi, profileApi } from '@/lib/api'
import type { EnterpriseProfile, EnterpriseScale } from '@/lib/api'
import { useAuth } from '@/providers/auth-provider'

/** 分区卡片样式（与政策库/工作台等页面视觉一致） */
const CARD_CLASS =
  'rounded-[18px] border border-[#e7e4df] bg-white p-6 shadow-[var(--shadow-card)]'

/** 企业规模选项 */
const SCALE_OPTIONS: { value: EnterpriseScale; label: string }[] = [
  { value: 'unspecified', label: '未填写' },
  { value: 'micro', label: '微型企业' },
  { value: 'small', label: '小型企业' },
  { value: 'medium', label: '中型企业' },
  { value: 'large', label: '大型企业' },
]

const SCALE_LABEL: Record<EnterpriseScale, string> = {
  unspecified: '未填写',
  micro: '微型企业',
  small: '小型企业',
  medium: '中型企业',
  large: '大型企业',
}

/** 常见资质快捷项 */
const QUALIFICATION_PRESETS = [
  '高新技术企业',
  '专精特新',
  '科技型中小企业',
  '创新型中小企业',
  '规上企业',
]

/** 空档案（默认地区无锡新吴区），用于首次加载前占位 */
const EMPTY_PROFILE: EnterpriseProfile = {
  company_name: '',
  province: '江苏省',
  city: '无锡市',
  district: '新吴区',
  industry: '',
  scale: 'unspecified',
  main_business: '',
  qualifications: [],
  tech_domains: [],
  keywords: [],
  contest_regions: [],
  established_date: '',
  total_staff: null,
  rd_staff: null,
  registered_capital_wan: null,
  annual_revenue_wan: null,
  rd_investment_wan: null,
  invention_patents: null,
  other_ip_count: null,
  updated_at: '',
}

/** 档案是否为空（尚未填写企业名称视为空档案） */
function isProfileEmpty(p: EnterpriseProfile): boolean {
  return !p.company_name.trim()
}

/** 数值字段是否已填写（区分"未填写"与 0） */
function hasNumber(v: number | null | undefined): v is number {
  return v !== null && v !== undefined
}

/**
 * 档案完整度（0-100）：按对下游匹配/资质差距分析有意义的字段加权统计。
 * 省/市/区有默认值，不计入。
 */
function completeness(p: EnterpriseProfile): number {
  const checks: boolean[] = [
    !!p.company_name.trim(),
    !!p.industry.trim(),
    p.scale !== 'unspecified',
    !!p.main_business.trim(),
    p.qualifications.length > 0,
    p.tech_domains.length > 0,
    p.keywords.length > 0,
    !!p.established_date,
    hasNumber(p.total_staff),
    hasNumber(p.rd_staff),
    hasNumber(p.registered_capital_wan),
    hasNumber(p.annual_revenue_wan),
    hasNumber(p.rd_investment_wan),
    hasNumber(p.invention_patents),
    hasNumber(p.other_ip_count),
  ]
  const filled = checks.filter(Boolean).length
  return Math.round((filled / checks.length) * 100)
}

function formatNumber(v: number | null): string {
  return hasNumber(v) ? v.toLocaleString('zh-CN') : '—'
}

function formatDateLabel(v: string): string {
  if (!v) return '—'
  const parsed = new Date(v)
  return Number.isNaN(parsed.getTime()) ? v : parsed.toLocaleDateString('zh-CN')
}

/** 数值字段输入（编辑态）：空串↔null 互转，非负 */
function NumberField({
  label,
  value,
  unit,
  step,
  placeholder,
  onChange,
}: {
  label: string
  value: number | null
  unit?: string
  step?: number
  placeholder?: string
  onChange: (next: number | null) => void
}) {
  return (
    <Field>
      <FieldLabel>
        {label}
        {unit && <span className="ml-1 text-xs text-muted-foreground">（{unit}）</span>}
      </FieldLabel>
      <Input
        type="number"
        min={0}
        step={step ?? 1}
        value={value === null || value === undefined ? '' : value}
        placeholder={placeholder ?? '未填写'}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === '') {
            onChange(null)
            return
          }
          const parsed = Number(raw)
          onChange(Number.isFinite(parsed) && parsed >= 0 ? parsed : null)
        }}
      />
    </Field>
  )
}

/** 标签输入（编辑态）：回车或失焦添加，去重 */
function TagInput({
  label,
  description,
  placeholder,
  values,
  presets,
  onChange,
}: {
  label: string
  description?: string
  placeholder: string
  values: string[]
  presets?: string[]
  onChange: (next: string[]) => void
}) {
  const [draft, setDraft] = useState('')

  const addTag = (raw: string) => {
    const tag = raw.trim()
    if (!tag || values.includes(tag)) {
      setDraft('')
      return
    }
    onChange([...values, tag])
    setDraft('')
  }

  const removeTag = (tag: string) => onChange(values.filter((v) => v !== tag))

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag(draft)
    }
  }

  const availablePresets = (presets ?? []).filter((p) => !values.includes(p))

  return (
    <Field>
      <FieldLabel>{label}</FieldLabel>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {values.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1">
              {tag}
              <button
                type="button"
                className="cursor-pointer text-muted-foreground hover:text-destructive"
                onClick={() => removeTag(tag)}
                aria-label={`移除 ${tag}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => addTag(draft)}
      />
      {availablePresets.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {availablePresets.map((preset) => (
            <Badge
              key={preset}
              variant="outline"
              className="cursor-pointer hover:bg-accent"
              onClick={() => addTag(preset)}
            >
              + {preset}
            </Badge>
          ))}
        </div>
      )}
      {description && <FieldDescription className="text-xs">{description}</FieldDescription>}
    </Field>
  )
}

/** 参赛关注地区多选（编辑态）：选项来自已接入赛事来源的地区，点击切换选中 */
function ContestRegionPicker({
  values,
  onChange,
}: {
  values: string[]
  onChange: (next: string[]) => void
}) {
  const [options, setOptions] = useState<string[]>([])
  const [loadingOptions, setLoadingOptions] = useState(true)

  useEffect(() => {
    // 选项 = 实际有赛事入库的地区去重(数据驱动)；创客中国等来源"一源多地区"，
    // 且只显示真有赛事的地区更贴合体验。来源下线后已选值仍保留可退选。
    policyApi
      .listContestRegions()
      .then((regions) => setOptions(regions))
      .catch(() => setOptions([]))
      .finally(() => setLoadingOptions(false))
  }, [])

  const toggle = (region: string) =>
    onChange(values.includes(region) ? values.filter((v) => v !== region) : [...values, region])

  // 已选但不在当前选项里的地区(如来源调整后)也要展示，保证可退选
  const allChips = [...options, ...values.filter((v) => !options.includes(v))]

  return (
    <Field>
      <FieldLabel>参赛关注地区</FieldLabel>
      {loadingOptions ? (
        <span className="text-xs text-muted-foreground">加载可选地区…</span>
      ) : allChips.length === 0 ? (
        <span className="text-xs text-muted-foreground">暂无已接入的赛事地区来源。</span>
      ) : (
        <div className="flex flex-wrap gap-2">
          {allChips.map((region) => {
            const selected = values.includes(region)
            return (
              <Badge
                key={region}
                variant={selected ? 'default' : 'outline'}
                className="cursor-pointer select-none hover:opacity-85"
                onClick={() => toggle(region)}
              >
                {selected ? '✓ ' : ''}
                {region}
              </Badge>
            )
          })}
        </div>
      )}
      <FieldDescription className="text-xs">
        比赛可异地参加，与企业所在地相互独立。不选＝不限地区；可选地区随赛事来源接入自动扩充。
      </FieldDescription>
    </Field>
  )
}

/** 查看态：只读标签云（空时弱化提示） */
function TagCloud({ values }: { values: string[] }) {
  if (values.length === 0) {
    return <span className="text-sm text-[#98a2b3]">未填写</span>
  }
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((tag) => (
        <Badge key={tag} variant="secondary" className="rounded-full px-3 py-1 text-sm font-normal">
          {tag}
        </Badge>
      ))}
    </div>
  )
}

/** 查看态：一项经营/研发指标（数据卡） */
function MetricCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  const empty = value === '—'
  return (
    <div className="rounded-2xl border border-[#eceae6] bg-[#fafafa] px-4 py-3">
      <div className="text-xs text-[#8b92a0]">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${empty ? 'text-[#cbd0d8]' : 'text-[#202939]'}`}>
        {value}
        {!empty && unit && <span className="ml-1 text-xs font-normal text-[#8b92a0]">{unit}</span>}
      </div>
    </div>
  )
}

/**
 * 企业档案页：以企业为主体的主动服务链路源头。
 *
 * 默认进"查看态"（企业名片式展示）；owner/admin 点「编辑」切换到表单态，
 * 保存提交后切回查看态、取消则放弃改动。租户内成员均可查看，编辑限 owner/admin
 * （后端二次校验）。默认地区为无锡新吴区。
 */
export default function EnterpriseProfilePage() {
  const { role } = useAuth()
  const canEdit = role === 'owner' || role === 'admin'

  const [profile, setProfile] = useState<EnterpriseProfile>(EMPTY_PROFILE)
  const [draft, setDraft] = useState<EnterpriseProfile>(EMPTY_PROFILE)
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const fetchingRef = useRef(false)

  const fetchProfile = useCallback(() => {
    if (fetchingRef.current) return
    fetchingRef.current = true
    setLoading(true)
    profileApi
      .get()
      .then((data) => setProfile(data ?? EMPTY_PROFILE))
      .catch((err) => {
        console.error('[EnterpriseProfile] 获取企业档案失败:', err)
        toast.error(err instanceof Error ? err.message : '获取企业档案失败')
      })
      .finally(() => {
        setLoading(false)
        fetchingRef.current = false
      })
  }, [])

  useEffect(() => {
    fetchProfile()
  }, [fetchProfile])

  const empty = isProfileEmpty(profile)
  const score = useMemo(() => completeness(profile), [profile])

  const startEdit = () => {
    setDraft(profile)
    setMode('edit')
  }

  const cancelEdit = () => setMode('view')

  const patch = <K extends keyof EnterpriseProfile>(key: K, value: EnterpriseProfile[K]) =>
    setDraft((prev) => ({ ...prev, [key]: value }))

  const handleSave = async () => {
    setSaving(true)
    try {
      const { updated_at: _updatedAt, ...payload } = draft
      void _updatedAt
      const saved = await profileApi.update(payload)
      setProfile(saved)
      setMode('view')
      toast.success('企业档案已保存')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存企业档案失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col bg-[#f8f8f7]">
      {/* 头部 */}
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <div className="min-w-0">
            <h1 className="truncate font-serif text-lg font-semibold tracking-tight text-[#1c2127]">企业档案</h1>
            <p className="hidden text-xs text-[#778090] sm:block">
              {canEdit
                ? '完善企业档案，作为后续政策匹配与主动推送的依据。'
                : '仅组织所有者 / 管理员可编辑企业档案。'}
            </p>
          </div>
        </div>
        {canEdit &&
          (mode === 'view' ? (
            <Button
              className="cursor-pointer rounded-xl"
              variant="outline"
              onClick={startEdit}
              disabled={loading}
            >
              <Pencil className="size-4" />
              {empty ? '完善档案' : '编辑'}
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="cursor-pointer rounded-xl bg-white"
                onClick={cancelEdit}
                disabled={saving}
              >
                取消
              </Button>
              <Button className="cursor-pointer rounded-xl" onClick={handleSave} disabled={saving}>
                {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                保存
              </Button>
            </div>
          ))}
      </header>

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[#778090]">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : mode === 'edit' ? (
          <EditForm draft={draft} patch={patch} />
        ) : empty ? (
          <EmptyState canEdit={canEdit} onStart={startEdit} />
        ) : (
          <ProfileView profile={profile} score={score} />
        )}
      </div>
    </div>
  )
}

/** 空档案占位（尚未填写时） */
function EmptyState({ canEdit, onStart }: { canEdit: boolean; onStart: () => void }) {
  return (
    <div className="mx-auto max-w-[760px]">
      <div className={`${CARD_CLASS} flex flex-col items-center gap-4 py-16 text-center`}>
        <div className="grid size-14 place-items-center rounded-2xl bg-[#eef8f8] text-[#287174]">
          <Building2 className="size-7" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-[#202939]">尚未填写企业档案</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#778090]">
            企业档案是政策匹配、资质差距分析和工作台主动推送的依据。
            {canEdit ? '完善后即可在工作台看到为你筛选的政策与资质机会。' : '请联系组织所有者 / 管理员填写。'}
          </p>
        </div>
        {canEdit && (
          <Button className="cursor-pointer rounded-xl" onClick={onStart}>
            <Pencil className="size-4" />
            开始填写
          </Button>
        )}
      </div>
    </div>
  )
}

/** 查看态：企业名片式展示 */
function ProfileView({ profile, score }: { profile: EnterpriseProfile; score: number }) {
  const region = [profile.province, profile.city, profile.district].filter(Boolean).join(' / ')

  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-4">
      {/* Hero 名片 */}
      <div className={CARD_CLASS}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-[#eef8f8] text-[#287174]">
              <Building2 className="size-7" />
            </div>
            <div className="min-w-0">
              <h2 className="font-serif text-2xl font-semibold leading-tight tracking-tight text-[#1c2127]">
                {profile.company_name}
              </h2>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[#667085]">
                <span className="inline-flex items-center gap-1">
                  <MapPin className="size-4 text-[#98a2b3]" />
                  {region || '未填写'}
                </span>
                {profile.industry && <span>· {profile.industry}</span>}
                {profile.scale !== 'unspecified' && (
                  <Badge variant="outline" className="rounded-full">
                    {SCALE_LABEL[profile.scale]}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          {profile.updated_at && (
            <div className="text-right text-xs text-[#98a2b3]">
              最后更新
              <div className="mt-0.5 text-[#778090]">{formatDateLabel(profile.updated_at)}</div>
            </div>
          )}
        </div>

        {/* 完整度 */}
        <div className="mt-5 rounded-2xl border border-[#eceae6] bg-[#fafafa] px-4 py-3">
          <div className="flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1 font-medium text-[#566070]">
              <Sparkles className="size-3.5 text-[#287174]" />
              档案完整度
            </span>
            <span className="font-semibold text-[#202939]">{score}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#e8e6e2]">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${score}%` }}
            />
          </div>
          {score < 100 && (
            <p className="mt-2 text-xs text-[#98a2b3]">
              补全经营与研发指标，可启用更精准的资质申报差距分析。
            </p>
          )}
        </div>

        {profile.main_business && (
          <div className="mt-5">
            <div className="text-xs font-semibold text-[#8b92a0]">主营业务</div>
            <p className="mt-1.5 whitespace-pre-wrap text-sm leading-7 text-[#475467]">
              {profile.main_business}
            </p>
          </div>
        )}
      </div>

      {/* 资质与领域 */}
      <div className={CARD_CLASS}>
        <div className="mb-4 flex items-center gap-2 text-base font-bold text-[#202939]">
          <Award className="size-5 text-[#287174]" />
          资质与领域
        </div>
        <div className="flex flex-col gap-4">
          <div>
            <div className="mb-2 text-xs font-semibold text-[#8b92a0]">已有资质</div>
            <TagCloud values={profile.qualifications} />
          </div>
          <div>
            <div className="mb-2 flex items-center gap-1 text-xs font-semibold text-[#8b92a0]">
              <Tags className="size-3.5" />
              技术 / 产品领域
            </div>
            <TagCloud values={profile.tech_domains} />
          </div>
          <div>
            <div className="mb-2 text-xs font-semibold text-[#8b92a0]">关键词标签</div>
            <TagCloud values={profile.keywords} />
          </div>
          <div>
            <div className="mb-2 flex items-center gap-1 text-xs font-semibold text-[#8b92a0]">
              <Trophy className="size-3.5" />
              参赛关注地区
            </div>
            {profile.contest_regions.length === 0 ? (
              <span className="text-sm text-[#98a2b3]">不限地区（未选择）</span>
            ) : (
              <TagCloud values={profile.contest_regions} />
            )}
          </div>
        </div>
      </div>

      {/* 经营与研发指标 */}
      <div className={CARD_CLASS}>
        <div className="mb-1 flex items-center gap-2 text-base font-bold text-[#202939]">
          <TrendingUp className="size-5 text-[#287174]" />
          经营与研发指标
        </div>
        <p className="mb-4 text-xs text-[#98a2b3]">用于资质申报机会的条件差距分析（成立年限、研发占比、研发投入强度、知识产权等）。</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <MetricCard label="成立 / 注册日期" value={formatDateLabel(profile.established_date)} />
          <MetricCard label="员工总数" value={formatNumber(profile.total_staff)} unit="人" />
          <MetricCard label="研发人员数" value={formatNumber(profile.rd_staff)} unit="人" />
          <MetricCard
            label="注册资本"
            value={formatNumber(profile.registered_capital_wan)}
            unit="万元"
          />
          <MetricCard
            label="上年度营业收入"
            value={formatNumber(profile.annual_revenue_wan)}
            unit="万元"
          />
          <MetricCard
            label="上年度研发投入"
            value={formatNumber(profile.rd_investment_wan)}
            unit="万元"
          />
          <MetricCard label="发明专利数" value={formatNumber(profile.invention_patents)} unit="件" />
          <MetricCard label="其他知识产权数" value={formatNumber(profile.other_ip_count)} unit="件" />
        </div>
      </div>
    </div>
  )
}

/** 编辑态：表单（沿用原有分区字段，绑定 draft） */
function EditForm({
  draft,
  patch,
}: {
  draft: EnterpriseProfile
  patch: <K extends keyof EnterpriseProfile>(key: K, value: EnterpriseProfile[K]) => void
}) {
  const [keywordSuggestions, setKeywordSuggestions] = useState<string[]>([])
  const [suggesting, setSuggesting] = useState(false)

  /** 从主营业务/行业自述提取候选关键词，排除已填项，作为关键词字段的快捷添加 */
  const onSuggestKeywords = async () => {
    const text = `${draft.main_business} ${draft.industry}`.trim()
    if (!text) {
      toast.error('请先填写主营业务或所属行业')
      return
    }
    setSuggesting(true)
    try {
      const exclude = [...draft.keywords, ...draft.tech_domains, ...draft.qualifications]
      const { suggestions } = await profileApi.suggestKeywords(text, exclude)
      setKeywordSuggestions(suggestions)
      toast[suggestions.length ? 'success' : 'info'](
        suggestions.length ? `提取到 ${suggestions.length} 个候选关键词` : '未提取到新候选词',
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '关键词提取失败')
    } finally {
      setSuggesting(false)
    }
  }

  return (
    <div className="mx-auto max-w-[760px]">
      <FieldGroup className="gap-4">
        <div className={CARD_CLASS}>
          <FieldSet>
            <FieldLegend className="text-base font-bold text-[#202939]">基本信息</FieldLegend>

            <Field>
              <FieldLabel htmlFor="company_name">企业名称</FieldLabel>
              <Input
                id="company_name"
                value={draft.company_name}
                placeholder="请输入企业全称"
                onChange={(e) => patch('company_name', e.target.value)}
              />
            </Field>

            <Field>
              <FieldLabel>所在地</FieldLabel>
              <div className="grid grid-cols-3 gap-2">
                <Input
                  value={draft.province}
                  placeholder="省"
                  onChange={(e) => patch('province', e.target.value)}
                />
                <Input
                  value={draft.city}
                  placeholder="市"
                  onChange={(e) => patch('city', e.target.value)}
                />
                <Input
                  value={draft.district}
                  placeholder="区/县"
                  onChange={(e) => patch('district', e.target.value)}
                />
              </div>
              <FieldDescription className="text-xs">
                经营地决定可享受的区/市/省级政策，默认无锡新吴区。
              </FieldDescription>
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field>
                <FieldLabel htmlFor="industry">所属行业</FieldLabel>
                <Input
                  id="industry"
                  value={draft.industry}
                  placeholder="如：智能制造、软件信息服务"
                  onChange={(e) => patch('industry', e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="scale">企业规模</FieldLabel>
                <select
                  id="scale"
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                  value={draft.scale}
                  onChange={(e) => patch('scale', e.target.value as EnterpriseScale)}
                >
                  {SCALE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <Field>
              <FieldLabel htmlFor="main_business">主营业务简介</FieldLabel>
              <Textarea
                id="main_business"
                value={draft.main_business}
                placeholder="简述企业主营业务、核心产品与技术方向"
                rows={4}
                onChange={(e) => patch('main_business', e.target.value)}
              />
            </Field>
          </FieldSet>
        </div>

        <div className={CARD_CLASS}>
          <FieldSet>
            <FieldLegend className="text-base font-bold text-[#202939]">资质与领域</FieldLegend>

            <TagInput
              label="已有资质"
              description="回车添加，或点击下方常见资质快捷添加。"
              placeholder="输入资质后回车，如：高新技术企业"
              values={draft.qualifications}
              presets={QUALIFICATION_PRESETS}
              onChange={(next) => patch('qualifications', next)}
            />

            <TagInput
              label="技术 / 产品领域"
              placeholder="输入领域后回车，如：工业机器人"
              values={draft.tech_domains}
              onChange={(next) => patch('tech_domains', next)}
            />

            <div className="flex items-center justify-between gap-2 pt-1">
              <span className="text-xs text-muted-foreground">
                关键词越贴合业务，匹配到的政策越准。可从主营业务智能提取。
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="cursor-pointer rounded-lg"
                onClick={onSuggestKeywords}
                disabled={suggesting}
              >
                {suggesting ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                智能提取关键词
              </Button>
            </div>

            <TagInput
              label="关键词标签"
              description={keywordSuggestions.length ? '点击下方候选词快捷添加。' : undefined}
              placeholder="输入关键词后回车，如：自动化"
              values={draft.keywords}
              presets={keywordSuggestions}
              onChange={(next) => patch('keywords', next)}
            />
          </FieldSet>
        </div>

        <div className={CARD_CLASS}>
          <FieldSet>
            <FieldLegend className="text-base font-bold text-[#202939]">参赛关注地区</FieldLegend>
            <p className="-mt-1 mb-1 text-xs text-muted-foreground">
              工作台「赛事机会」按此过滤大赛/比赛通知。
            </p>
            <ContestRegionPicker
              values={draft.contest_regions}
              onChange={(next) => patch('contest_regions', next)}
            />
          </FieldSet>
        </div>

        <div className={CARD_CLASS}>
          <FieldSet>
            <FieldLegend className="text-base font-bold text-[#202939]">经营与研发指标</FieldLegend>
            <p className="-mt-1 mb-1 text-xs text-muted-foreground">
              用于资质申报机会的条件差距分析（如成立年限、研发人员占比、研发投入强度、知识产权数量）。按企业实际据实填写，留空表示暂未提供。
            </p>

            <Field>
              <FieldLabel htmlFor="established_date">成立 / 注册日期</FieldLabel>
              <Input
                id="established_date"
                type="date"
                value={draft.established_date}
                onChange={(e) => patch('established_date', e.target.value)}
              />
              <FieldDescription className="text-xs">
                许多资质要求“成立满 N 年”，据此判断年限是否达标。
              </FieldDescription>
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <NumberField
                label="员工总数"
                unit="人"
                value={draft.total_staff}
                onChange={(v) => patch('total_staff', v)}
              />
              <NumberField
                label="研发人员数"
                unit="人"
                value={draft.rd_staff}
                onChange={(v) => patch('rd_staff', v)}
              />
              <NumberField
                label="注册资本"
                unit="万元"
                step={0.01}
                value={draft.registered_capital_wan}
                onChange={(v) => patch('registered_capital_wan', v)}
              />
              <NumberField
                label="上年度营业收入"
                unit="万元"
                step={0.01}
                value={draft.annual_revenue_wan}
                onChange={(v) => patch('annual_revenue_wan', v)}
              />
              <NumberField
                label="上年度研发投入"
                unit="万元"
                step={0.01}
                value={draft.rd_investment_wan}
                onChange={(v) => patch('rd_investment_wan', v)}
              />
              <NumberField
                label="发明专利数"
                unit="件"
                value={draft.invention_patents}
                onChange={(v) => patch('invention_patents', v)}
              />
              <NumberField
                label="其他知识产权数"
                unit="件（实用新型/软著/外观等）"
                value={draft.other_ip_count}
                onChange={(v) => patch('other_ip_count', v)}
              />
            </div>
          </FieldSet>
        </div>
      </FieldGroup>
    </div>
  )
}
