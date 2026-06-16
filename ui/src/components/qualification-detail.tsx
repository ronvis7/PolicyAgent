'use client'

import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  CONDITION_STATUS_LABEL,
  QUALIFICATION_LEVEL_LABEL,
  qualificationApi,
  type ConditionStatus,
  type QualificationDetail,
  type QualificationGap,
} from '@/lib/api'

/** 详情区块（标题 + 列表/文本） */
function Section({ title, items, text }: { title: string; items?: string[]; text?: string }) {
  if ((!items || items.length === 0) && !text) return null
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-semibold text-foreground/80">{title}</h3>
      {items && items.length > 0 ? (
        <ul className="space-y-1 pl-1">
          {items.map((it, i) => (
            <li key={i} className="text-sm leading-6 text-foreground/90">
              · {it}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm leading-6 text-foreground/90">{text}</p>
      )}
    </div>
  )
}

/** 单条硬条件状态图标 */
function StatusIcon({ status }: { status: ConditionStatus }) {
  if (status === 'met') return <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
  if (status === 'unmet') return <XCircle className="size-4 shrink-0 text-red-600" />
  return <HelpCircle className="size-4 shrink-0 text-amber-500" />
}

/** 条件差距分析区块（能力②）：逐条核验 + 待确认/待补 + 前置缺口。 */
function GapSection({ qualKey }: { qualKey: string }) {
  const [gap, setGap] = useState<QualificationGap | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      setGap(await qualificationApi.getGap(qualKey))
    } catch {
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [qualKey])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> 正在按企业档案分析条件差距…
      </div>
    )
  }
  if (failed || !gap) return null

  const hasStructured = gap.checks.length > 0

  return (
    <div className="space-y-2 rounded-md border bg-muted/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground/80">条件差距分析（基于企业档案）</h3>
        {hasStructured && (
          <div className="flex gap-1.5 text-xs">
            <span className="text-emerald-600">达标 {gap.met_count}</span>
            <span className="text-red-600">不达标 {gap.unmet_count}</span>
            <span className="text-amber-500">待确认 {gap.unknown_count}</span>
          </div>
        )}
      </div>

      {gap.summary && <p className="text-xs text-muted-foreground">{gap.summary}</p>}

      {hasStructured && (
        <ul className="space-y-1.5">
          {gap.checks.map((c, i) => (
            <li key={i} className="flex items-start gap-2 text-sm leading-6">
              <span className="mt-0.5">
                <StatusIcon status={c.status} />
              </span>
              <span className="text-foreground/90">
                {c.detail || `${c.label}（${CONDITION_STATUS_LABEL[c.status]}）`}
              </span>
            </li>
          ))}
        </ul>
      )}

      {gap.unknown_count > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-300">
          「待确认」表示企业档案尚未填写对应数据，请到「企业档案 → 经营与研发指标」补充后再看分析。
        </p>
      )}

      {gap.prerequisites_missing.length > 0 && (
        <Section title="缺失前置资质" items={gap.prerequisites_missing} />
      )}
      {gap.manual_review.length > 0 && (
        <Section title="需结合材料人工确认" items={gap.manual_review} />
      )}
    </div>
  )
}

/** 资质详情展示（工作台 Feed 与资质机会页复用）。免责声明 banner 强制置顶。 */
export function QualificationDetailView({ detail }: { detail: QualificationDetail }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{QUALIFICATION_LEVEL_LABEL[detail.level] ?? detail.level}</Badge>
        {detail.category && <Badge variant="outline">{detail.category}</Badge>}
        {detail.region && <Badge variant="outline">{detail.region}</Badge>}
        {detail.issuer && <span className="text-xs text-muted-foreground">{detail.issuer}</span>}
      </div>

      {/* 风险纪律：免责声明 + 末次核对日期，醒目置顶，严禁当权威输出 */}
      <div className="flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200">
        <AlertTriangle className="size-4 shrink-0 mt-0.5" />
        <div className="text-xs leading-5">
          <p>{detail.disclaimer}</p>
          {detail.last_reviewed && <p className="mt-1 opacity-80">末次核对：{detail.last_reviewed}</p>}
        </div>
      </div>

      {/* 能力②：条件差距分析（按当前租户档案现算） */}
      <GapSection qualKey={detail.key} />

      <Section title="核心条件（概要）" items={detail.key_conditions} />
      <Section title="主要材料（概要）" items={detail.materials} />
      <Section title="申报时间" text={detail.timing} />
      <Section title="政策依据" text={detail.policy_basis} />
      <Section title="主要价值" text={detail.benefit} />
    </div>
  )
}
