'use client'

import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { isFileProcessing, type FileStatus } from '@/lib/api/knowledge'

/** 状态 -> 中文文案 */
const STATUS_LABEL: Record<FileStatus, string> = {
  uploaded: '已上传',
  parsing: '解析中',
  parsed: '已解析',
  indexing: '向量化中',
  indexed: '可检索',
  error_parsing: '解析失败',
  error_indexing: '向量化失败',
}

/** 状态 -> Badge 样式 */
const STATUS_VARIANT: Record<
  FileStatus,
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  uploaded: 'secondary',
  parsing: 'secondary',
  parsed: 'secondary',
  indexing: 'secondary',
  indexed: 'default',
  error_parsing: 'destructive',
  error_indexing: 'destructive',
}

/**
 * 知识库文件状态徽标
 * 处理中状态附带旋转图标，便于用户感知后台进度。
 */
export function FileStatusBadge({ status }: { status: FileStatus }) {
  const processing = isFileProcessing(status)
  return (
    <Badge variant={STATUS_VARIANT[status]}>
      {processing && <Loader2 className="animate-spin" />}
      {STATUS_LABEL[status]}
    </Badge>
  )
}
