'use client'

import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { QUALIFICATION_LEVEL_LABEL, type QualificationDetail } from '@/lib/api'

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

      <Section title="核心条件（概要）" items={detail.key_conditions} />
      <Section title="主要材料（概要）" items={detail.materials} />
      <Section title="申报时间" text={detail.timing} />
      <Section title="政策依据" text={detail.policy_basis} />
      <Section title="主要价值" text={detail.benefit} />
    </div>
  )
}
