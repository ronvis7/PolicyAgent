import { get, post } from "./fetch";
import { API_BASE_URL } from "./base";
import { getAccessToken } from "../auth-storage";
import { refreshAccessToken } from "./token-refresh";
import type { FileInfo, FileUploadParams } from "./types";

/**
 * 下载文件流（带鉴权）。
 *
 * 文件下载端点受 JWT 保护，必须带 Authorization 头；裸 fetch 不会自动携带本地令牌，
 * 会被后端判为 401 Unauthorized。这里注入 Bearer 令牌，并在 401 时刷新令牌后重试一次，
 * 与 request()/createSSEStream 的鉴权行为保持一致。
 */
async function fetchFileBlob(fileId: string, isRetry = false): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/files/${fileId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (response.status === 401 && !isRetry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return fetchFileBlob(fileId, true);
    }
  }

  if (!response.ok) {
    throw new Error(`下载失败: ${response.statusText || response.status}`);
  }

  return response.blob();
}

/**
 * 文件模块 API
 */
export const fileApi = {
  /**
   * 上传文件
   * @param params 上传参数，包含文件和可选的会话 ID
   * @returns 文件信息
   */
  uploadFile: async (params: FileUploadParams): Promise<FileInfo> => {
    const formData = new FormData();
    formData.append("file", params.file);
    
    if (params.session_id) {
      formData.append("session_id", params.session_id);
    }

    return post<FileInfo>("/files", formData);
  },

  /**
   * 获取文件信息
   * @param fileId 文件 ID
   * @returns 文件信息
   */
  getFileInfo: (fileId: string): Promise<FileInfo> => {
    return get<FileInfo>(`/files/${fileId}`);
  },

  /**
   * 下载文件（带鉴权，返回 Blob 对象）
   * @param fileId 文件 ID
   * @returns Blob 对象
   */
  downloadFile: (fileId: string): Promise<Blob> => {
    return fetchFileBlob(fileId);
  },
};

