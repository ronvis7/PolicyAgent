import { API_BASE_URL } from "./base";
import { getAccessToken } from "../auth-storage";
import { refreshAccessToken } from "./token-refresh";

/** 政策匹配简报下载结果：PDF 字节 + 后端给出的文件名 */
export type BriefDownload = {
  blob: Blob;
  filename: string;
};

/**
 * 从 Content-Disposition 解析后端给的文件名（RFC 5987 `filename*=utf-8''...`），
 * 解析失败回退到一个稳妥的默认名。
 */
function parseFilename(header: string | null): string {
  const fallback = "政策匹配简报.pdf";
  if (!header) return fallback;
  const match = header.match(/filename\*=utf-8''([^;]+)/i);
  if (match?.[1]) {
    try {
      return decodeURIComponent(match[1]);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

/**
 * 拉取政策匹配简报 PDF（带鉴权）。
 *
 * 报告端点受 JWT 保护，必须带 Authorization 头；裸 fetch 不会自动携带本地令牌，
 * 与 fileApi.downloadFile 一致地注入 Bearer，并在 401 时刷新令牌后重试一次。
 */
async function fetchBrief(isRetry = false): Promise<BriefDownload> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/reports/policy-brief`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (response.status === 401 && !isRetry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return fetchBrief(true);
    }
  }

  if (!response.ok) {
    throw new Error(`导出失败: ${response.statusText || response.status}`);
  }

  const filename = parseFilename(response.headers.get("Content-Disposition"));
  return { blob: await response.blob(), filename };
}

export const reportApi = {
  /** 下载当前租户的政策匹配简报 PDF（限当前租户，由后端按令牌作用域） */
  downloadBrief: (): Promise<BriefDownload> => fetchBrief(),
};
