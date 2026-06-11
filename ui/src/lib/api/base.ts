/**
 * API 基础配置（被 fetch 封装与 token 刷新共享，避免重复定义）
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

/** 默认请求超时（毫秒） */
export const API_TIMEOUT = 30000;
