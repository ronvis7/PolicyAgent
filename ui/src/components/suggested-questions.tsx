'use client'

import {cn} from '@/lib/utils'
import {Award, FileSearch, Sparkles, Target} from 'lucide-react'
import {suggestedQuestions} from '@/config/app.config'

interface SuggestedQuestionsProps {
  className?: string
  onQuestionClick?: (question: string) => void
}

// 与推荐问题一一对应的图标（按序，超出回落到通用图标）
const QUESTION_ICONS = [Award, Target, FileSearch, Sparkles]

export function SuggestedQuestions({className, onQuestionClick}: SuggestedQuestionsProps) {
  const handleClick = (question: string) => {
    onQuestionClick?.(question)
  }

  return (
    <div className={cn('grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-3', className)}>
      {suggestedQuestions.map((question, index) => {
        const Icon = QUESTION_ICONS[index % QUESTION_ICONS.length]
        return (
          <button
            key={index}
            type="button"
            className="group flex cursor-pointer items-center gap-3 rounded-2xl border border-border bg-card px-4 py-3 text-left text-sm text-muted-foreground shadow-[var(--shadow-card)] transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[var(--shadow-hover)]"
            onClick={() => handleClick(question)}
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-primary transition-colors group-hover:bg-primary group-hover:text-white">
              <Icon className="size-4"/>
            </span>
            <span className="leading-snug break-words">{question}</span>
          </button>
        )
      })}
    </div>
  )
}
