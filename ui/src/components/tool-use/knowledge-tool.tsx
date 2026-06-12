'use client'

import { BookOpen } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface KnowledgeToolProps {
  label: string
  onClick?: () => void
}

export function KnowledgeTool({ label, onClick }: KnowledgeToolProps) {
  return <ToolBadge icon={BookOpen} label={label} onClick={onClick} />
}
