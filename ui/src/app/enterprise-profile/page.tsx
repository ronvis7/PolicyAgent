'use client'

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { toast } from 'sonner'
import { Loader2, Save, X } from 'lucide-react'
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

/** 表单分区卡片样式（与政策库/工作台等页面视觉一致） */
const CARD_CLASS =
  'rounded-[18px] border border-[#e5e2de] bg-white p-6 shadow-[0_10px_30px_rgba(16,24,40,.04)]'

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

/** 数值字段输入：空串↔null 互转，非负，禁用时展示"未填写" */
function NumberField({
  label,
  value,
  unit,
  step,
  placeholder,
  disabled,
  onChange,
}: {
  label: string
  value: number | null
  unit?: string
  step?: number
  placeholder?: string
  disabled: boolean
  onChange: (next: number | null) => void
}) {
  return (
    <Field>
      <FieldLabel>
        {label}
        {unit && <span className="ml-1 text-xs text-muted-foreground">（{unit}）</span>}
      </FieldLabel>
      {disabled ? (
        <span className="text-sm text-muted-foreground">
          {value === null || value === undefined ? '未填写' : value}
        </span>
      ) : (
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
      )}
    </Field>
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
  onChange,
}: {
  label: string
  description?: string
  placeholder: string
  values: string[]
  presets?: string[]
  disabled: boolean
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
 * 默认地区为无锡新吴区。Agent 联网增强（①b）后续接入。
 */
export default function EnterpriseProfilePage() {
  const { role } = useAuth()
  const canEdit = role === 'owner' || role === 'admin'

  const [profile, setProfile] = useState<EnterpriseProfile>(EMPTY_PROFILE)
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

  const patch = <K extends keyof EnterpriseProfile>(key: K, value: EnterpriseProfile[K]) =>
    setProfile((prev) => ({ ...prev, [key]: value }))

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
    <div className="h-full flex flex-col bg-[#f8f8f7]">
      {/* 头部 */}
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e5e2de] bg-[#f8f8f7]/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-[#202939]">企业档案</h1>
            <p className="hidden text-xs text-[#778090] sm:block">
              {canEdit
                ? '完善企业档案，作为后续政策匹配与主动推送的依据。'
                : '仅组织所有者 / 管理员可编辑企业档案。'}
            </p>
          </div>
        </div>
        {canEdit && (
          <Button className="cursor-pointer rounded-xl" onClick={handleSave} disabled={loading || saving}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            保存
          </Button>
        )}
      </header>

      {/* 表单 */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[#778090]">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : (
          <div className="max-w-[760px] mx-auto">
            <FieldGroup className="gap-4">
              <div className={CARD_CLASS}>
              <FieldSet>
                <FieldLegend className="text-base font-bold text-[#202939]">基本信息</FieldLegend>

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
                    <FieldLabel htmlFor="industry">所属行业</FieldLabel>
                    <Input
                      id="industry"
                      value={profile.industry}
                      placeholder="如：智能制造、软件信息服务"
                      disabled={!canEdit}
                      onChange={(e) => patch('industry', e.target.value)}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="scale">企业规模</FieldLabel>
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
                  <FieldLabel htmlFor="main_business">主营业务简介</FieldLabel>
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
              </div>

              <div className={CARD_CLASS}>
              <FieldSet>
                <FieldLegend className="text-base font-bold text-[#202939]">资质与领域</FieldLegend>

                <TagInput
                  label="已有资质"
                  description="回车添加，或点击下方常见资质快捷添加。"
                  placeholder="输入资质后回车，如：高新技术企业"
                  values={profile.qualifications}
                  presets={QUALIFICATION_PRESETS}
                  disabled={!canEdit}
                  onChange={(next) => patch('qualifications', next)}
                />

                <TagInput
                  label="技术 / 产品领域"
                  placeholder="输入领域后回车，如：工业机器人"
                  values={profile.tech_domains}
                  disabled={!canEdit}
                  onChange={(next) => patch('tech_domains', next)}
                />

                <TagInput
                  label="关键词标签"
                  placeholder="输入关键词后回车，如：自动化"
                  values={profile.keywords}
                  disabled={!canEdit}
                  onChange={(next) => patch('keywords', next)}
                />
              </FieldSet>
              </div>

              <div className={CARD_CLASS}>
              <FieldSet>
                <FieldLegend className="text-base font-bold text-[#202939]">
                  经营与研发指标
                </FieldLegend>
                <p className="-mt-1 mb-1 text-xs text-muted-foreground">
                  用于资质申报机会的条件差距分析（如成立年限、研发人员占比、研发投入强度、知识产权数量）。按企业实际据实填写，留空表示暂未提供。
                </p>

                <Field>
                  <FieldLabel htmlFor="established_date">成立 / 注册日期</FieldLabel>
                  <Input
                    id="established_date"
                    type="date"
                    value={profile.established_date}
                    disabled={!canEdit}
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
                    value={profile.total_staff}
                    disabled={!canEdit}
                    onChange={(v) => patch('total_staff', v)}
                  />
                  <NumberField
                    label="研发人员数"
                    unit="人"
                    value={profile.rd_staff}
                    disabled={!canEdit}
                    onChange={(v) => patch('rd_staff', v)}
                  />
                  <NumberField
                    label="注册资本"
                    unit="万元"
                    step={0.01}
                    value={profile.registered_capital_wan}
                    disabled={!canEdit}
                    onChange={(v) => patch('registered_capital_wan', v)}
                  />
                  <NumberField
                    label="上年度营业收入"
                    unit="万元"
                    step={0.01}
                    value={profile.annual_revenue_wan}
                    disabled={!canEdit}
                    onChange={(v) => patch('annual_revenue_wan', v)}
                  />
                  <NumberField
                    label="上年度研发投入"
                    unit="万元"
                    step={0.01}
                    value={profile.rd_investment_wan}
                    disabled={!canEdit}
                    onChange={(v) => patch('rd_investment_wan', v)}
                  />
                  <NumberField
                    label="发明专利数"
                    unit="件"
                    value={profile.invention_patents}
                    disabled={!canEdit}
                    onChange={(v) => patch('invention_patents', v)}
                  />
                  <NumberField
                    label="其他知识产权数"
                    unit="件（实用新型/软著/外观等）"
                    value={profile.other_ip_count}
                    disabled={!canEdit}
                    onChange={(v) => patch('other_ip_count', v)}
                  />
                </div>
              </FieldSet>
              </div>
            </FieldGroup>
          </div>
        )}
      </div>
    </div>
  )
}
