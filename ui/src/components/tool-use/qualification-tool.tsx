'use client'

import { Award } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface QualificationToolProps {
  label: string
  onClick?: () => void
}

export function QualificationTool({ label, onClick }: QualificationToolProps) {
  return <ToolBadge icon={Award} label={label} onClick={onClick} />
}
