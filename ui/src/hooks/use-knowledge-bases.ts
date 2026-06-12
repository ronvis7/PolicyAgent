'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  knowledgeApi,
  type CreateKnowledgeBaseParams,
  type KnowledgeBase,
} from '@/lib/api/knowledge'

/**
 * 知识库列表 Hook
 *
 * 负责加载当前租户的知识库列表，并提供新建/删除操作。
 * 操作成功后本地以不可变方式更新列表，避免整表重拉。
 */
export function useKnowledgeBases() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await knowledgeApi.listKnowledgeBases()
      setKnowledgeBases(list)
    } catch (e) {
      const message = e instanceof Error ? e.message : '加载知识库列表失败'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const createKnowledgeBase = useCallback(
    async (params: CreateKnowledgeBaseParams): Promise<KnowledgeBase> => {
      const kb = await knowledgeApi.createKnowledgeBase(params)
      setKnowledgeBases((prev) => [kb, ...prev])
      return kb
    },
    []
  )

  const deleteKnowledgeBase = useCallback(async (kbId: string) => {
    await knowledgeApi.deleteKnowledgeBase(kbId)
    setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== kbId))
  }, [])

  return {
    knowledgeBases,
    loading,
    error,
    reload,
    createKnowledgeBase,
    deleteKnowledgeBase,
  }
}
