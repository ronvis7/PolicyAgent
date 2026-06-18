'use client'

import { useState } from 'react'
import type { ComponentType } from 'react'
import { FileText, Landmark, Lock, Network } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import type {
  CreateKnowledgeBaseParams,
  KnowledgeBase,
  KnowledgeBaseType,
} from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'

type CreateKbDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (params: CreateKnowledgeBaseParams) => Promise<KnowledgeBase>
}

// 知识库类型与后端 KnowledgeBaseType 对齐(general / policy)，反映真实能力而非向量库后端选型。
const KNOWLEDGE_TYPES: {
  key: KnowledgeBaseType
  title: string
  description: string
  tag: string
  icon: ComponentType<{ className?: string }>
}[] = [
  {
    key: 'general',
    title: '通用文档库',
    description: '上传政策文件、企业材料或案例文档，供智能体检索问答',
    tag: '文档上传',
    icon: FileText,
  },
  {
    key: 'policy',
    title: '私有政策库',
    description: '从公开政策库收藏政策入库，沉淀本企业关注的政策原文',
    tag: '政策收藏',
    icon: Landmark,
  },
]

export function CreateKbDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateKbDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedType, setSelectedType] = useState<KnowledgeBaseType>('general')
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setName('')
    setDescription('')
    setSelectedType('general')
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
      await onCreate({ name: trimmed, description: description.trim(), type: selectedType })
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
            <div className="grid gap-3 md:grid-cols-2">
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
              className="flex h-12 items-center justify-between rounded-xl border border-[#e5e7eb] bg-[#fafafa] px-4 text-sm text-[#202939]"
            >
              <span>组织 Embedding 模型 · 1024 维（统一锁定）</span>
              <Network className="size-4 text-[#9ca3af]" />
            </div>
            <p className="text-xs leading-5 text-[#9ca3af]">
              向量维度统一锁定为 1024 以保证检索一致；模型由平台设定，可在「设置 · 向量模型」中配置组织自有密钥。
            </p>
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

          <section className="flex items-start gap-3 rounded-xl border border-[#ececec] bg-[#fafafa] px-4 py-3">
            <Lock className="mt-0.5 size-4 shrink-0 text-[#9ca3af]" />
            <span className="text-sm leading-6 text-[#525252]">
              知识库仅本组织可见，文档与切片按组织隔离存储，其他组织无法访问。
            </span>
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
