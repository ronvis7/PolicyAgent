import { del, get, post } from "./fetch";

// ==================== 收藏结果类型 ====================

/** 批量收藏结果：成功收藏与跳过(缺失/无正文)的数量 */
export type CollectPoliciesResult = {
  collected_count: number;
  skipped_count: number;
};

// ==================== 知识库模块类型 ====================

/**
 * 知识库文件处理状态机（与后端 FileStatus 对齐）
 * 正常流转：uploaded -> parsing -> parsed -> indexing -> indexed
 * 异常分支：error_parsing / error_indexing
 */
export type FileStatus =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "indexing"
  | "indexed"
  | "error_parsing"
  | "error_indexing";

/** 知识库 */
export type KnowledgeBase = {
  id: string;
  tenant_id: string;
  owner_id: string | null;
  name: string;
  description: string;
  type: string;
  embedding_model: string;
  updated_at: string;
  created_at: string;
};

/** 知识库文件（含处理状态） */
export type KnowledgeFile = {
  id: string;
  tenant_id: string;
  knowledge_base_id: string;
  owner_id: string | null;
  file_id: string | null;
  filename: string;
  status: FileStatus;
  error_message: string;
  chunk_count: number;
  updated_at: string;
  created_at: string;
};

/** 知识库类型：general=通用文档库 / policy=私有政策库(收藏公开政策) */
export type KnowledgeBaseType = "general" | "policy";

/** 新建知识库请求参数 */
export type CreateKnowledgeBaseParams = {
  name: string;
  description?: string;
  type?: KnowledgeBaseType;
};

// ==================== 知识库模块 API ====================

export const knowledgeApi = {
  /** 列出当前租户的全部知识库 */
  listKnowledgeBases: (): Promise<KnowledgeBase[]> => {
    return get<KnowledgeBase[]>("/knowledge-bases");
  },

  /** 在当前租户下新建知识库 */
  createKnowledgeBase: (
    params: CreateKnowledgeBaseParams
  ): Promise<KnowledgeBase> => {
    return post<KnowledgeBase>("/knowledge-bases", {
      name: params.name,
      description: params.description ?? "",
      type: params.type ?? "general",
    });
  },

  /** 获取知识库详情 */
  getKnowledgeBase: (kbId: string): Promise<KnowledgeBase> => {
    return get<KnowledgeBase>(`/knowledge-bases/${kbId}`);
  },

  /** 删除知识库（级联删除文件与切片） */
  deleteKnowledgeBase: (kbId: string): Promise<null> => {
    return del<null>(`/knowledge-bases/${kbId}`);
  },

  /** 列出知识库下的文件及其处理状态 */
  listFiles: (kbId: string): Promise<KnowledgeFile[]> => {
    return get<KnowledgeFile[]>(`/knowledge-bases/${kbId}/files`);
  },

  /** 上传文件到知识库（解析/向量化在后台异步进行） */
  uploadFile: (kbId: string, file: File): Promise<KnowledgeFile> => {
    const formData = new FormData();
    formData.append("file", file);
    return post<KnowledgeFile>(`/knowledge-bases/${kbId}/files`, formData);
  },

  /** 收藏一篇公开政策到私有政策库（向量化在后台异步进行） */
  collectPolicy: (kbId: string, policyId: string): Promise<KnowledgeFile> => {
    return post<KnowledgeFile>(`/knowledge-bases/${kbId}/policies`, {
      policy_id: policyId,
    });
  },

  /** 批量收藏多篇公开政策到私有政策库（逐篇 best-effort，向量化后台异步进行） */
  collectPolicies: (
    kbId: string,
    policyIds: string[]
  ): Promise<CollectPoliciesResult> => {
    return post<CollectPoliciesResult>(`/knowledge-bases/${kbId}/policies/batch`, {
      policy_ids: policyIds,
    });
  },

  /** 各知识库的文件数 {kb_id: count}（单次分组查询，供列表卡片展示真实数量） */
  fileCounts: (): Promise<Record<string, number>> => {
    return get<Record<string, number>>("/knowledge-bases/file-counts");
  },
};

/** 文件状态是否仍在处理中（用于决定是否继续轮询） */
export function isFileProcessing(status: FileStatus): boolean {
  return (
    status === "uploaded" ||
    status === "parsing" ||
    status === "parsed" ||
    status === "indexing"
  );
}

/** 文件状态是否为失败 */
export function isFileFailed(status: FileStatus): boolean {
  return status === "error_parsing" || status === "error_indexing";
}
