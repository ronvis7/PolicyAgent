'use client'

import { useState } from 'react'
import type { ComponentType } from 'react'
import { Building2, Database, GitBranch, Network } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type {
  CreateKnowledgeBaseParams,
  KnowledgeBase,
} from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'

type CreateKbDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (params: CreateKnowledgeBaseParams) => Promise<KnowledgeBase>
}

type KbKind = 'chroma' | 'milvus' | 'lightrag'

const KNOWLEDGE_TYPES: {
  key: KbKind
  title: string
  description: string
  tag: string
  icon: ComponentType<{ className?: string }>
}[] = [
  {
    key: 'chroma',
    title: 'Chroma',
    description: '基于 ChromaDB 的轻量向量库',
    tag: '轻量向量',
    icon: Database,
  },
  {
    key: 'milvus',
    title: 'Milvus',
    description: '面向生产环境的向量库',
    tag: '生产部署',
    icon: Building2,
  },
  {
    key: 'lightrag',
    title: 'LightRAG',
    description: '面向图结构线索的检索组织',
    tag: '图结构索引',
    icon: GitBranch,
  },
]

export function CreateKbDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateKbDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedType, setSelectedType] = useState<KbKind>('chroma')
  const [isPrivate, setIsPrivate] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setName('')
    setDescription('')
    setSelectedType('chroma')
    setIsPrivate(true)
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) reset()
    onOpenChange(next)
  }

  const handleSubmit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('请输入知识库名称')
      return
    }
    setSubmitting(true)
    try {
      await onCreate({ name: trimmed, description: description.trim() })
      toast.success('知识库创建成功')
      reset()
      onOpenChange(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '创建知识库失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-auto rounded-2xl p-0 sm:max-w-[960px]">
        <DialogHeader className="border-b border-[#ececec] px-7 py-5 text-left">
          <DialogTitle className="text-lg font-semibold text-[#1f2937]">
            新建知识库
          </DialogTitle>
          <DialogDescription className="text-sm text-[#737373]">
            创建后即可上传政策文件、企业材料或案例文档。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 px-7 py-5">
          <section className="space-y-3">
            <Label className="text-sm font-semibold text-[#202939]">知识库类型</Label>
            <div className="grid gap-3 md:grid-cols-3">
              {KNOWLEDGE_TYPES.map((item) => {
                const Icon = item.icon
                const active = selectedType === item.key
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={cn(
                      'rounded-2xl border p-5 text-left transition',
                      active
                        ? 'border-[#c9a7e8] bg-[#fbf6ff] shadow-[0_0_0_1px_rgba(201,167,232,.32)]'
                        : 'border-[#ececec] bg-white hover:border-[#d6d6d6]',
                    )}
                    onClick={() => setSelectedType(item.key)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn('grid size-10 place-items-center rounded-xl', active ? 'bg-[#f0e6fb] text-[#7c3aed]' : 'bg-[#f5f5f5] text-[#4b5563]')}>
                        <Icon className="size-5" />
                      </div>
                      <div>
                        <div className="font-semibold text-[#202939]">{item.title}</div>
                        <div className="mt-1 text-sm text-[#737373]">{item.description}</div>
                      </div>
                    </div>
                    <span className={cn('mt-4 inline-flex rounded-lg px-2.5 py-1 text-xs font-medium', active ? 'bg-[#efe0ff] text-[#7c3aed]' : 'bg-[#eef6f8] text-[#287174]')}>
                      {item.tag}
                    </span>
                  </button>
                )
              })}
            </div>
          </section>

          <section className="space-y-2">
            <Label htmlFor="kb-name" className="text-sm font-semibold text-[#202939]">知识库名称</Label>
            <Input
              id="kb-name"
              value={name}
              maxLength={255}
              placeholder="新建知识库名称"
              onChange={(e) => setName(e.target.value)}
              disabled={submitting}
              className="h-12 rounded-xl"
            />
          </section>

          <section className="space-y-2">
            <Label htmlFor="kb-model" className="text-sm font-semibold text-[#202939]">嵌入模型</Label>
            <div
              id="kb-model"
              className="flex h-12 items-center justify-between rounded-xl border border-[#e5e7eb] bg-white px-4 text-sm text-[#202939]"
            >
              <span>siliconflow/Pro/BAAI/bge-m3 (1024)</span>
              <Network className="size-4 text-[#9ca3af]" />
            </div>
          </section>

          <section className="space-y-3">
            <div>
              <Label htmlFor="kb-desc" className="text-sm font-semibold text-[#202939]">知识库描述</Label>
              <p className="mt-2 text-sm leading-6 text-[#737373]">
                描述会帮助智能体判断何时使用该知识库，建议说明资料范围、适用场景和业务目标。
              </p>
            </div>
            <Textarea
              id="kb-desc"
              value={description}
              maxLength={1024}
              placeholder="新建知识库描述"
              onChange={(e) => setDescription(e.target.value)}
              disabled={submitting}
              className="min-h-36 rounded-xl"
            />
          </section>

          <section className="space-y-3">
            <Label className="text-sm font-semibold text-[#202939]">隐私设置</Label>
            <div className="flex items-center gap-3">
              <Switch checked={isPrivate} onCheckedChange={setIsPrivate} disabled={submitting} />
              <span className="text-sm text-[#525252]">设置为私有知识库</span>
            </div>
          </section>
        </div>

        <DialogFooter className="border-t border-[#ececec] px-7 py-4">
          <Button
            variant="outline"
            className="cursor-pointer rounded-xl"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            className="cursor-pointer rounded-xl bg-[#287174] hover:bg-[#1f5f62]"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
