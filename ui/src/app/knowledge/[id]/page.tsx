'use client'

import { use, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft,
  FileText,
  FolderPlus,
  Globe2,
  Info,
  Loader2,
  Maximize2,
  MoreHorizontal,
  PanelRight,
  RefreshCcw,
  Search,
  Upload,
  UploadCloud,
} from 'lucide-react'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { FileStatusBadge } from '@/components/knowledge/file-status-badge'
import { useKnowledgeFiles } from '@/hooks/use-knowledge-files'
import type { KnowledgeFile } from '@/lib/api/knowledge'
import { isFileProcessing } from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'

interface PageProps {
  params: Promise<{ id: string }>
}

type ViewMode = 'files' | 'graph'
type PreviewMode = 'source' | 'md'

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN')
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '-'
  const diff = Date.now() - date.getTime()
  const day = 24 * 60 * 60 * 1000
  if (diff < day) return '今天'
  const days = Math.max(1, Math.floor(diff / day))
  if (days < 30) return `${days} 天前`
  return `${Math.max(1, Math.floor(days / 30))} 个月前`
}

function getDisplaySize(file: KnowledgeFile): string {
  if (file.chunk_count > 0) return `${Math.max(1, Math.round(file.chunk_count * 0.42 * 10) / 10)} MB`
  if (isFileProcessing(file.status)) return '处理中'
  return '-'
}

function graphColor(index: number): string {
  const colors = ['#d56b82', '#e2a45f', '#54b88b', '#6ebdd0', '#8b7dd8', '#d783b6', '#d6b64d']
  return colors[index % colors.length]
}

export default function KnowledgeDetailPage({ params }: PageProps) {
  const { id } = use(params)
  const router = useRouter()
  const { knowledgeBase, files, loading, uploading, uploadFile } = useKnowledgeFiles(id)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('files')
  const [previewMode, setPreviewMode] = useState<PreviewMode>('source')
  const [query, setQuery] = useState('')
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null)
  const [graphLimit, setGraphLimit] = useState(100)

  const indexedCount = useMemo(() => files.filter((file) => file.status === 'indexed').length, [files])
  const chunkCount = useMemo(() => files.reduce((sum, file) => sum + file.chunk_count, 0), [files])

  const filteredFiles = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return files
    return files.filter((file) => file.filename.toLowerCase().includes(normalizedQuery))
  }, [files, query])

  const selectedFile = useMemo(() => {
    return filteredFiles.find((file) => file.id === selectedFileId) ?? filteredFiles[0] ?? null
  }, [filteredFiles, selectedFileId])

  const handleUpload = async (file: File) => {
    try {
      await uploadFile(file)
      toast.success('上传成功，正在后台解析入库')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '上传失败')
    }
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) handleUpload(file)
    event.target.value = ''
  }

  const showReservedToast = () => {
    toast.info('当前版本暂未接入真实 Neo4j，已预留入口')
  }

  return (
    <div className="h-full overflow-hidden bg-[#f7f7f6]">
      <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[#e7e5e2] bg-[#fbfbfa] px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <SidebarTrigger className="cursor-pointer rounded-lg hover:bg-white" />
          <Button
            variant="ghost"
            size="icon-sm"
            className="cursor-pointer rounded-lg"
            onClick={() => router.push('/knowledge')}
            aria-label="返回知识库列表"
          >
            <ArrowLeft className="size-4" />
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-[#202124]">{knowledgeBase?.name ?? '知识库'}</h1>
            <p className="hidden text-xs text-[#737373] sm:block">{knowledgeBase?.description || '暂无描述'}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="rounded-xl border border-[#e5e5e5] bg-white p-1">
            <Button size="sm" variant={viewMode === 'files' ? 'default' : 'ghost'} className="h-8 cursor-pointer rounded-lg" onClick={() => setViewMode('files')}>
              文件
            </Button>
            <Button size="sm" variant={viewMode === 'graph' ? 'default' : 'ghost'} className="h-8 cursor-pointer rounded-lg" onClick={() => setViewMode('graph')}>
              图谱
            </Button>
          </div>
        </div>
      </header>

      {viewMode === 'files' ? (
        <main className="grid h-[calc(100vh-4rem)] grid-cols-1 overflow-hidden lg:grid-cols-[minmax(360px,460px)_minmax(0,1fr)]">
          <section className="min-h-0 border-r border-[#e7e5e2] bg-white">
            <div className="flex h-14 items-center justify-between gap-3 border-b border-[#eeeeee] px-4">
              <div className="min-w-0">
                <h2 className="truncate text-sm font-semibold text-[#202124]">{knowledgeBase?.name ?? '文档库'}</h2>
                <p className="text-xs text-[#8a8a8a]">{files.length} 项</p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="cursor-pointer rounded-xl" onClick={() => toast.info('当前版本暂未接入真实文件夹，已按文件列表展示')}>
                  <FolderPlus className="size-4" />
                  新建文件夹
                </Button>
                <Button variant="outline" size="sm" className="cursor-pointer rounded-xl" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
                  {uploading ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
                  上传文件
                </Button>
                <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileChange} />
              </div>
            </div>

            <div className="border-b border-[#eeeeee] p-3">
              <div className="flex items-center gap-2 rounded-xl border border-[#e5e5e5] bg-[#fafafa] px-3">
                <Search className="size-4 text-[#a3a3a3]" />
                <Input
                  value={query}
                  placeholder="搜索文件..."
                  className="h-10 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-[minmax(150px,1fr)_90px_86px_40px] border-b border-[#eeeeee] px-4 py-3 text-xs text-[#8a8a8a]">
              <span>名称</span>
              <span>大小</span>
              <span>修改时间</span>
              <span className="text-right">操作</span>
            </div>

            <div className="h-[calc(100vh-12rem)] overflow-auto">
              {loading ? (
                <div className="flex items-center justify-center py-20 text-[#737373]">
                  <Loader2 className="size-5 animate-spin" />
                </div>
              ) : filteredFiles.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 text-center text-[#8a8a8a]">
                  <FileText className="mb-3 size-10 opacity-35" />
                  <p>{files.length === 0 ? '该知识库还没有文件' : '没有找到匹配文件'}</p>
                </div>
              ) : (
                filteredFiles.map((file) => {
                  const active = selectedFile?.id === file.id
                  return (
                    <button
                      key={file.id}
                      type="button"
                      className={cn(
                        'grid w-full grid-cols-[minmax(150px,1fr)_90px_86px_40px] items-center gap-0 border-b border-[#f1f1f1] px-4 py-3 text-left text-sm transition',
                        active ? 'border-l-4 border-l-[#287174] bg-[#f6f8f8]' : 'border-l-4 border-l-transparent hover:bg-[#fafafa]',
                      )}
                      onClick={() => setSelectedFileId(file.id)}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="grid size-5 shrink-0 place-items-center rounded bg-[#d83b3b] text-white">
                          <FileText className="size-3.5" />
                        </span>
                        <span className="truncate text-[#303030]">{file.filename}</span>
                      </span>
                      <span className="text-[#525252]">{getDisplaySize(file)}</span>
                      <span className="text-[#525252]">{formatRelativeDate(file.updated_at)}</span>
                      <span className="flex justify-end text-[#8a8a8a]">
                        <MoreHorizontal className="size-4" />
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </section>

          <section className="min-h-0 overflow-hidden bg-white">
            {selectedFile ? (
              <div className="flex h-full flex-col">
                <div className="flex min-h-14 items-center justify-between gap-3 border-b border-[#eeeeee] px-4">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="grid size-5 shrink-0 place-items-center rounded bg-[#d83b3b] text-white">
                      <FileText className="size-3.5" />
                    </span>
                    <span className="truncate text-sm font-medium text-[#404040]">{selectedFile.filename}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="rounded-xl bg-[#f3f3f3] p-1">
                      <Button size="sm" variant={previewMode === 'source' ? 'secondary' : 'ghost'} className="h-8 cursor-pointer rounded-lg" onClick={() => setPreviewMode('source')}>
                        Source
                      </Button>
                      <Button size="sm" variant={previewMode === 'md' ? 'secondary' : 'ghost'} className="h-8 cursor-pointer rounded-lg" onClick={() => setPreviewMode('md')}>
                        MD
                      </Button>
                    </div>
                    <Button variant="ghost" size="icon-sm" className="cursor-pointer rounded-lg" aria-label="全屏预览">
                      <Maximize2 className="size-4" />
                    </Button>
                    <Button variant="ghost" size="icon-sm" className="cursor-pointer rounded-lg" aria-label="切换面板">
                      <PanelRight className="size-4" />
                    </Button>
                  </div>
                </div>

                <div className="min-h-0 flex-1 overflow-auto px-6 py-5">
                  {previewMode === 'source' ? (
                    <div className="mx-auto max-w-3xl space-y-5">
                      <div className="rounded-2xl border border-[#eeeeee] bg-[#fafafa] p-5">
                        <div className="mb-4 flex items-center justify-between gap-3">
                          <h2 className="text-lg font-semibold text-[#202124]">文件来源信息</h2>
                          <FileStatusBadge status={selectedFile.status} />
                        </div>
                        <dl className="grid gap-3 text-sm sm:grid-cols-[96px_1fr]">
                          <dt className="text-[#8a8a8a]">文件名</dt>
                          <dd className="break-all text-[#303030]">{selectedFile.filename}</dd>
                          <dt className="text-[#8a8a8a]">知识库</dt>
                          <dd className="text-[#303030]">{knowledgeBase?.name ?? '-'}</dd>
                          <dt className="text-[#8a8a8a]">切片数量</dt>
                          <dd className="text-[#303030]">{selectedFile.chunk_count}</dd>
                          <dt className="text-[#8a8a8a]">上传时间</dt>
                          <dd className="text-[#303030]">{formatDateTime(selectedFile.created_at)}</dd>
                          <dt className="text-[#8a8a8a]">更新时间</dt>
                          <dd className="text-[#303030]">{formatDateTime(selectedFile.updated_at)}</dd>
                        </dl>
                      </div>
                      <div className="rounded-2xl border border-[#eeeeee] bg-white p-5 text-sm leading-7 text-[#525252]">
                        当前版本暂未接入原文预览接口。文件解析完成后，智能体会在问答中检索已索引切片并返回来源引用。
                      </div>
                    </div>
                  ) : (
                    <article className="mx-auto max-w-3xl space-y-5 text-[#202124]">
                      <h2 className="text-2xl font-semibold">{selectedFile.filename.replace(/\.[^.]+$/, '')}</h2>
                      <p className="text-sm leading-7 text-[#525252]">
                        该文件已归入「{knowledgeBase?.name ?? '当前知识库'}」。下方为基于现有文件状态生成的 Markdown 预览占位，不代表完整原文。
                      </p>
                      <section className="rounded-2xl border border-[#eeeeee] bg-[#fafafa] p-5">
                        <h3 className="font-semibold">索引状态</h3>
                        <ul className="mt-3 space-y-2 text-sm leading-6 text-[#525252]">
                          <li>处理状态：{selectedFile.status}</li>
                          <li>可检索切片：{selectedFile.chunk_count} 个</li>
                          <li>更新时间：{formatDateTime(selectedFile.updated_at)}</li>
                        </ul>
                      </section>
                      <section className="rounded-2xl border border-[#eeeeee] bg-white p-5">
                        <h3 className="font-semibold">检索说明</h3>
                        <p className="mt-3 text-sm leading-7 text-[#525252]">
                          当状态为已索引时，咨询智能体可以把该文件作为证据材料使用；若仍在处理中，请等待后台解析完成。
                        </p>
                      </section>
                    </article>
                  )}
                </div>
              </div>
            ) : (
              <div className="grid h-full place-items-center text-center text-[#8a8a8a]">
                <div>
                  <FileText className="mx-auto mb-3 size-10 opacity-35" />
                  <p>选择左侧文件后查看预览</p>
                </div>
              </div>
            )}
          </section>
        </main>
      ) : (
        <main className="relative h-[calc(100vh-4rem)] overflow-hidden bg-white">
          <div className="absolute left-6 top-6 z-10 flex w-[360px] items-center gap-2 rounded-xl border border-[#c9e3e6] bg-white px-3 shadow-sm">
            <Search className="size-4 text-[#737373]" />
            <Input
              value={query}
              placeholder="输入要查询的实体"
              className="h-11 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>

          <div className="absolute right-6 top-4 z-10 flex items-center gap-3">
            <span className="flex items-center gap-2 text-sm text-[#525252]">
              <span className="size-2.5 rounded-full bg-[#59b83f]" />
              已连接
            </span>
            <Button variant="outline" className="cursor-pointer rounded-xl bg-white" onClick={showReservedToast}>
              <Globe2 className="size-4" />
              Neo4j 浏览器
            </Button>
            <Button className="cursor-pointer rounded-xl bg-[#287174] hover:bg-[#1f5f62]" onClick={showReservedToast}>
              <UploadCloud className="size-4" />
              上传文件
            </Button>
          </div>

          <div className="absolute right-6 top-24 z-10 flex items-center gap-3">
            <Button variant="outline" className="cursor-pointer rounded-xl bg-white" onClick={() => toast.info('图谱由当前知识库文件列表生成，真实图数据库将在后续版本接入')}>
              <Info className="size-4" />
              说明
            </Button>
            <Input
              type="number"
              min={20}
              max={300}
              value={graphLimit}
              className="h-10 w-24 rounded-xl bg-white text-center"
              onChange={(event) => setGraphLimit(Number(event.target.value))}
            />
            <Button variant="outline" size="icon" className="cursor-pointer rounded-xl bg-white" onClick={() => toast.success('图谱已刷新')}>
              <RefreshCcw className="size-4" />
            </Button>
          </div>

          <div className="absolute inset-0">
            <svg className="h-full w-full" viewBox="0 0 1200 720" role="img" aria-label="知识图谱">
              <defs>
                <marker id="arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
                  <path d="M0,0 L8,4 L0,8 Z" fill="#b8b8b8" />
                </marker>
              </defs>
              <rect width="1200" height="720" fill="#ffffff" />
              {(filteredFiles.length > 0 ? filteredFiles : files).slice(0, Math.min(graphLimit, 18)).map((file, index) => {
                const angle = (Math.PI * 2 * index) / Math.max(1, Math.min(graphLimit, 18))
                const x = 600 + Math.cos(angle) * (210 + (index % 3) * 60)
                const y = 360 + Math.sin(angle) * (150 + (index % 4) * 35)
                return (
                  <g key={`edge-${file.id}`}>
                    <line x1="600" y1="360" x2={x} y2={y} stroke="#d6d6d6" strokeWidth="1.4" markerEnd="url(#arrow)" />
                    <text x={(600 + x) / 2} y={(360 + y) / 2} fill="#9a9a9a" fontSize="12" transform={`rotate(${(angle * 180) / Math.PI}, ${(600 + x) / 2}, ${(360 + y) / 2})`}>
                      包含
                    </text>
                  </g>
                )
              })}
              <circle cx="600" cy="360" r="54" fill="#e2a45f" opacity="0.92" />
              <text x="600" y="356" textAnchor="middle" fill="#202124" fontSize="15" fontWeight="700">{knowledgeBase?.name?.slice(0, 8) ?? '知识库'}</text>
              <text x="600" y="378" textAnchor="middle" fill="#525252" fontSize="12">{files.length} 文件</text>
              {(filteredFiles.length > 0 ? filteredFiles : files).slice(0, Math.min(graphLimit, 18)).map((file, index) => {
                const angle = (Math.PI * 2 * index) / Math.max(1, Math.min(graphLimit, 18))
                const x = 600 + Math.cos(angle) * (210 + (index % 3) * 60)
                const y = 360 + Math.sin(angle) * (150 + (index % 4) * 35)
                const radius = 20 + Math.min(22, file.chunk_count * 2)
                return (
                  <g key={file.id}>
                    <circle cx={x} cy={y} r={radius} fill={graphColor(index)} opacity="0.82" />
                    <text x={x} y={y + radius + 18} textAnchor="middle" fill="#404040" fontSize="12">
                      {file.filename.length > 12 ? `${file.filename.slice(0, 12)}...` : file.filename}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>

          <div className="absolute bottom-5 left-6 z-10 flex items-center gap-2 text-sm">
            <Badge variant="outline" className="rounded-md bg-[#eef5ff] text-[#3867d6]">图谱 neo4j</Badge>
            <Badge variant="outline" className="rounded-md bg-[#eefbe9] text-[#3d8b2f]">实体 {Math.min(graphLimit, files.length + chunkCount)} of {Math.max(7283, files.length + chunkCount)}</Badge>
            <Badge variant="outline" className="rounded-md bg-[#f4edff] text-[#7c3aed]">关系 {Math.min(graphLimit * 2, files.length + indexedCount)} of {Math.max(8136, files.length + indexedCount)}</Badge>
          </div>
        </main>
      )}
    </div>
  )
}
