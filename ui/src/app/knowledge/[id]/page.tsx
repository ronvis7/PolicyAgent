'use client'

import { use, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, FileText, Loader2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { FileStatusBadge } from '@/components/knowledge/file-status-badge'
import { useKnowledgeFiles } from '@/hooks/use-knowledge-files'
import { isFileFailed } from '@/lib/api/knowledge'

interface PageProps {
  params: Promise<{ id: string }>
}

/** 格式化为本地日期时间 */
function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString()
}

/**
 * 知识库详情页：展示知识库信息、文件列表及其处理状态，支持上传新文件。
 * 存在处理中的文件时列表会自动轮询刷新（见 useKnowledgeFiles）。
 */
export default function KnowledgeDetailPage({ params }: PageProps) {
  const { id } = use(params)
  const router = useRouter()
  const { knowledgeBase, files, loading, uploading, uploadFile } =
    useKnowledgeFiles(id)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleUpload = async (file: File) => {
    try {
      await uploadFile(file)
      toast.success('上传成功，正在后台解析入库')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '上传失败')
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    // 允许重复上传同一文件
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <header className="flex items-center gap-2 w-full py-2 px-4 border-b">
        <SidebarTrigger className="cursor-pointer" />
        <Button
          variant="ghost"
          size="icon-sm"
          className="cursor-pointer"
          onClick={() => router.push('/knowledge')}
          aria-label="返回知识库列表"
        >
          <ArrowLeft className="size-4" />
        </Button>
        <h1 className="text-base font-semibold truncate">
          {knowledgeBase?.name ?? '知识库'}
        </h1>
      </header>

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-[900px] mx-auto">
          {/* 描述 */}
          {knowledgeBase?.description && (
            <p className="text-sm text-muted-foreground mb-4">
              {knowledgeBase.description}
            </p>
          )}

          {/* 上传区 */}
          <div
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 mb-6 transition-colors ${
              dragOver ? 'border-primary bg-primary/5' : 'border-border'
            }`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <Upload className="size-8 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-3">
              拖拽文件到此处，或点击下方按钮上传
            </p>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileChange}
            />
            <Button
              className="cursor-pointer"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  上传中...
                </>
              ) : (
                <>
                  <Upload className="size-4" />
                  选择文件
                </>
              )}
            </Button>
          </div>

          {/* 文件列表 */}
          {loading ? (
            <div className="flex items-center justify-center py-16 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : files.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
              <FileText className="size-10 mb-3 opacity-40" />
              <p>该知识库还没有文件</p>
            </div>
          ) : (
            <div className="rounded-lg border bg-white divide-y">
              {files.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  <FileText className="size-5 text-muted-foreground shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{file.filename}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {file.status === 'indexed' && file.chunk_count > 0
                        ? `${file.chunk_count} 个切片 · `
                        : ''}
                      上传于 {formatDateTime(file.created_at)}
                      {isFileFailed(file.status) && file.error_message
                        ? ` · ${file.error_message}`
                        : ''}
                    </div>
                  </div>
                  <FileStatusBadge status={file.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
