'use client'

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { toast } from 'sonner'
import { Building2, ExternalLink, Loader2, Save, Sparkles, X } from 'lucide-react'
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
import { profileApi } from '@/lib/api'
import type { EnterpriseProfile, EnterpriseScale } from '@/lib/api'
import { useAuth } from '@/providers/auth-provider'

/** 企业规模选项 */
const SCALE_OPTIONS: { value: EnterpriseScale; label: string }[] = [
  { value: 'unspecified', label: '未填写' },
  { value: 'micro', label: '微型企业' },
  { value: 'small', label: '小型企业' },
  { value: 'medium', label: '中型企业' },
  { value: 'large', label: '大型企业' },
]

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
  updated_at: '',
}

/** AI 补全来源链接：显示在字段标签旁，点开是引用网址 */
function SourceLink({ source }: { source?: string }) {
  if (!source) return null
  return (
    <a
      href={source}
      target="_blank"
      rel="noopener noreferrer"
      title={`AI 补全来源：${source}`}
      className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      <ExternalLink className="size-3" />
      来源
    </a>
  )
}

/** 标签输入：回车或失焦添加，去重；只读时仅展示 */
function TagInput({
  label,
  description,
  placeholder,
  values,
  presets,
  disabled,
  source,
  onChange,
}: {
  label: string
  description?: string
  placeholder: string
  values: string[]
  presets?: string[]
  disabled: boolean
  source?: string
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
      <FieldLabel className="flex items-center gap-2">
        {label}
        <SourceLink source={source} />
      </FieldLabel>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {values.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1">
              {tag}
              {!disabled && (
                <button
                  type="button"
                  className="cursor-pointer text-muted-foreground hover:text-destructive"
                  onClick={() => removeTag(tag)}
                  aria-label={`移除 ${tag}`}
                >
                  <X className="size-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
      )}
      {!disabled && (
        <>
          <Input
            value={draft}
            placeholder={placeholder}
            disabled={disabled}
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
        </>
      )}
      {disabled && values.length === 0 && (
        <span className="text-sm text-muted-foreground">未填写</span>
      )}
      {description && <FieldDescription className="text-xs">{description}</FieldDescription>}
    </Field>
  )
}

/**
 * 企业档案页：以企业为主体的主动服务链路源头。
 *
 * 租户内成员均可查看；编辑限组织 owner/admin（后端二次校验）。
 * 默认地区为无锡新吴区。owner/admin 可「AI 联网补全」（①b）自动检索建议后审阅保存。
 */
export default function EnterpriseProfilePage() {
  const { role } = useAuth()
  const canEdit = role === 'owner' || role === 'admin'

  const [profile, setProfile] = useState<EnterpriseProfile>(EMPTY_PROFILE)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [enriching, setEnriching] = useState(false)
  // 逐字段来源：字段名 → 来源 URL（AI 补全填入时记录，展示在字段旁）
  const [fieldSources, setFieldSources] = useState<Record<string, string>>({})
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

  const patch = <K extends keyof EnterpriseProfile>(key: K, value: EnterpriseProfile[K]) =>
    setProfile((prev) => ({ ...prev, [key]: value }))

  /** 标签并集去重，保持原顺序后追加新值 */
  const mergeTags = (existing: string[], incoming: string[]): string[] => {
    const seen = new Set(existing)
    return [...existing, ...incoming.filter((t) => !seen.has(t))]
  }

  const handleEnrich = async () => {
    const companyName = profile.company_name.trim()
    if (!companyName) {
      toast.warning('请先填写企业名称再使用联网补全')
      return
    }
    setEnriching(true)
    try {
      const e = await profileApi.enrich({
        company_name: companyName,
        province: profile.province,
        city: profile.city,
        district: profile.district,
      })
      // 非破坏式合并：已填标量保留，空缺才回填；标签取并集，供用户审阅后再保存
      setProfile((prev) => ({
        ...prev,
        industry: prev.industry || e.industry.value,
        scale: prev.scale === 'unspecified' && e.scale.value
          ? (e.scale.value as EnterpriseScale)
          : prev.scale,
        main_business: prev.main_business || e.main_business.value,
        qualifications: mergeTags(prev.qualifications, e.qualifications.values),
        tech_domains: mergeTags(prev.tech_domains, e.tech_domains.values),
        keywords: mergeTags(prev.keywords, e.keywords.values),
      }))
      // 记录各字段来源（仅 AI 实际给出值的字段；来源缺失则用首个总来源兜底）
      const fallback = e.sources[0] ?? ''
      const nextSources: Record<string, string> = {}
      if (e.industry.value) nextSources.industry = e.industry.source || fallback
      if (e.scale.value) nextSources.scale = e.scale.source || fallback
      if (e.main_business.value) nextSources.main_business = e.main_business.source || fallback
      if (e.qualifications.values.length) nextSources.qualifications = e.qualifications.source || fallback
      if (e.tech_domains.values.length) nextSources.tech_domains = e.tech_domains.source || fallback
      if (e.keywords.values.length) nextSources.keywords = e.keywords.source || fallback
      setFieldSources((prev) => ({ ...prev, ...nextSources }))

      const filledCount = Object.keys(nextSources).length
      if (e.note) {
        toast.warning(e.note)
      } else if (filledCount === 0) {
        toast.warning('AI 未能查到该企业的公开信息，请手动填写')
      } else {
        toast.success(`AI 已补全 ${filledCount} 项，请审阅后点击保存`)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '联网补全失败')
    } finally {
      setEnriching(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { updated_at: _updatedAt, ...payload } = profile
      void _updatedAt
      const saved = await profileApi.update(payload)
      setProfile(saved)
      toast.success('企业档案已保存')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存企业档案失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <header className="flex justify-between items-center w-full py-2 px-4 border-b">
        <div className="flex items-center gap-2">
          <SidebarTrigger className="cursor-pointer" />
          <h1 className="text-base font-semibold">企业档案</h1>
        </div>
        {canEdit && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="cursor-pointer"
              onClick={handleEnrich}
              disabled={loading || saving || enriching}
              title="以企业名联网检索并由 AI 补全档案建议"
            >
              {enriching ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              AI 联网补全
            </Button>
            <Button className="cursor-pointer" onClick={handleSave} disabled={loading || saving || enriching}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
              保存
            </Button>
          </div>
        )}
      </header>

      {/* 表单 */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : (
          <div className="max-w-[760px] mx-auto">
            <div className="mb-4 flex items-center gap-2 text-muted-foreground">
              <Building2 className="size-5" />
              <span className="text-sm">
                {canEdit
                  ? '完善企业档案，作为后续政策匹配与主动推送的依据。可点「AI 联网补全」自动检索后审阅保存。'
                  : '仅组织所有者/管理员可编辑企业档案。'}
              </span>
            </div>

            <FieldGroup>
              <FieldSet>
                <FieldLegend className="text-base font-bold text-gray-700">基本信息</FieldLegend>

                <Field>
                  <FieldLabel htmlFor="company_name">企业名称</FieldLabel>
                  <Input
                    id="company_name"
                    value={profile.company_name}
                    placeholder="请输入企业全称"
                    disabled={!canEdit}
                    onChange={(e) => patch('company_name', e.target.value)}
                  />
                </Field>

                <Field>
                  <FieldLabel>所在地</FieldLabel>
                  <div className="grid grid-cols-3 gap-2">
                    <Input
                      value={profile.province}
                      placeholder="省"
                      disabled={!canEdit}
                      onChange={(e) => patch('province', e.target.value)}
                    />
                    <Input
                      value={profile.city}
                      placeholder="市"
                      disabled={!canEdit}
                      onChange={(e) => patch('city', e.target.value)}
                    />
                    <Input
                      value={profile.district}
                      placeholder="区/县"
                      disabled={!canEdit}
                      onChange={(e) => patch('district', e.target.value)}
                    />
                  </div>
                  <FieldDescription className="text-xs">
                    经营地决定可享受的区/市/省级政策，默认无锡新吴区。
                  </FieldDescription>
                </Field>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field>
                    <FieldLabel htmlFor="industry" className="flex items-center gap-2">
                      所属行业
                      <SourceLink source={fieldSources.industry} />
                    </FieldLabel>
                    <Input
                      id="industry"
                      value={profile.industry}
                      placeholder="如：智能制造、软件信息服务"
                      disabled={!canEdit}
                      onChange={(e) => patch('industry', e.target.value)}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="scale" className="flex items-center gap-2">
                      企业规模
                      <SourceLink source={fieldSources.scale} />
                    </FieldLabel>
                    <select
                      id="scale"
                      className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                      value={profile.scale}
                      disabled={!canEdit}
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
                  <FieldLabel htmlFor="main_business" className="flex items-center gap-2">
                    主营业务简介
                    <SourceLink source={fieldSources.main_business} />
                  </FieldLabel>
                  <Textarea
                    id="main_business"
                    value={profile.main_business}
                    placeholder="简述企业主营业务、核心产品与技术方向"
                    rows={4}
                    disabled={!canEdit}
                    onChange={(e) => patch('main_business', e.target.value)}
                  />
                </Field>
              </FieldSet>

              <FieldSet>
                <FieldLegend className="text-base font-bold text-gray-700">资质与领域</FieldLegend>

                <TagInput
                  label="已有资质"
                  description="回车添加，或点击下方常见资质快捷添加。"
                  placeholder="输入资质后回车，如：高新技术企业"
                  values={profile.qualifications}
                  presets={QUALIFICATION_PRESETS}
                  disabled={!canEdit}
                  source={fieldSources.qualifications}
                  onChange={(next) => patch('qualifications', next)}
                />

                <TagInput
                  label="技术 / 产品领域"
                  placeholder="输入领域后回车，如：工业机器人"
                  values={profile.tech_domains}
                  disabled={!canEdit}
                  source={fieldSources.tech_domains}
                  onChange={(next) => patch('tech_domains', next)}
                />

                <TagInput
                  label="关键词标签"
                  placeholder="输入关键词后回车，如：自动化"
                  values={profile.keywords}
                  disabled={!canEdit}
                  source={fieldSources.keywords}
                  onChange={(next) => patch('keywords', next)}
                />
              </FieldSet>
            </FieldGroup>
          </div>
        )}
      </div>
    </div>
  )
}
