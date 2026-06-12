'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  knowledgeApi,
  isFileProcessing,
  type KnowledgeBase,
  type KnowledgeFile,
} from '@/lib/api/knowledge'

/** 仍有文件处理中时的列表轮询间隔（毫秒） */
const POLL_INTERVAL_MS = 3000

/**
 * 知识库详情 + 文件列表 Hook
 *
 * - 加载知识库详情与文件列表
 * - 提供上传操作（上传后立即刷新列表）
 * - 当存在处理中的文件时，自动按固定间隔轮询列表，直至全部进入终态
 */
export function useKnowledgeFiles(kbId: string) {
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null)
  const [files, setFiles] = useState<KnowledgeFile[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchFiles = useCallback(async () => {
    const list = await knowledgeApi.listFiles(kbId)
    setFiles(list)
    return list
  }, [kbId])

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [kb] = await Promise.all([
        knowledgeApi.getKnowledgeBase(kbId),
        fetchFiles(),
      ])
      setKnowledgeBase(kb)
    } catch (e) {
      const message = e instanceof Error ? e.message : '加载知识库失败'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [kbId, fetchFiles])

  useEffect(() => {
    reload()
  }, [reload])

  // 存在处理中的文件时启动轮询；进入终态后自动停止
  useEffect(() => {
    const hasProcessing = files.some((f) => isFileProcessing(f.status))
    if (!hasProcessing) return

    timerRef.current = setTimeout(() => {
      fetchFiles().catch(() => {
        // 轮询期间的瞬时错误不打断用户，下一轮重试
      })
    }, POLL_INTERVAL_MS)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [files, fetchFiles])

  const uploadFile = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        const created = await knowledgeApi.uploadFile(kbId, file)
        setFiles((prev) => [created, ...prev])
      } finally {
        setUploading(false)
      }
    },
    [kbId]
  )

  return {
    knowledgeBase,
    files,
    loading,
    uploading,
    error,
    reload,
    uploadFile,
  }
}
