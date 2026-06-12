'use client'

import { useState } from 'react'
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
} from '@/lib/api/knowledge'

type CreateKbDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (params: CreateKnowledgeBaseParams) => Promise<KnowledgeBase>
}

/**
 * 新建知识库弹窗
 * 名称必填，描述可选；提交成功后关闭并清空表单。
 */
export function CreateKbDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateKbDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setName('')
    setDescription('')
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
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">
            新建知识库
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            知识库用于归集政策文档，上传后系统会自动解析并建立向量索引。
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="kb-name">名称</Label>
            <Input
              id="kb-name"
              value={name}
              maxLength={255}
              placeholder="例如：研发费用加计扣除政策库"
              onChange={(e) => setName(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="kb-desc">描述（可选）</Label>
            <Textarea
              id="kb-desc"
              value={description}
              maxLength={1024}
              placeholder="简要说明该知识库的用途与范围"
              onChange={(e) => setDescription(e.target.value)}
              disabled={submitting}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            className="cursor-pointer"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            取消
          </Button>
          <Button
            className="cursor-pointer"
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
