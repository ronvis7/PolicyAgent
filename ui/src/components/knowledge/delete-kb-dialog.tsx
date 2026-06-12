'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

type DeleteKbDialogProps = {
  open: boolean
  kbName: string
  onOpenChange: (open: boolean) => void
  onConfirm: () => Promise<void>
}

/**
 * 删除知识库确认弹窗
 * 删除会级联清除该库下全部文件与向量切片，故需二次确认。
 */
export function DeleteKbDialog({
  open,
  kbName,
  onOpenChange,
  onConfirm,
}: DeleteKbDialogProps) {
  const [deleting, setDeleting] = useState(false)

  const handleConfirm = async () => {
    setDeleting(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">
            要删除知识库吗？
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground leading-relaxed">
            删除「{kbName}」后，该库下的所有文件与向量切片都将被永久删除，无法找回。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            className="cursor-pointer"
            onClick={() => onOpenChange(false)}
            disabled={deleting}
          >
            取消
          </Button>
          <Button
            variant="destructive"
            className="cursor-pointer"
            onClick={handleConfirm}
            disabled={deleting}
          >
            {deleting ? '删除中...' : '确认删除'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
