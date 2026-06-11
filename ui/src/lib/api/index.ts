/**
 * API 模块统一导出
 */

// 核心 fetch 封装
export {
  request,
  get,
  post,
  put,
  del,
  createSSEConnection,
  createSSEStream,
  parseSSEStream,
  ApiError,
} from "./fetch";

// 类型定义
export type {
  ApiResponse,
  SessionStatus,
  ExecutionStatus,
  ToolEventStatus,
  MCPTransport,
  LLMConfig,
  AgentConfig,
  ListMCPServerItem,
  MCPServerConfig,
  MCPConfig,
  MCPServersData,
  ListA2AServerItem,
  A2AServersData,
  CreateA2AServerParams,
  FileInfo,
  FileUploadParams,
  Session,
  SessionDetail,
  SessionsData,
  CreateSessionParams,
  ChatMessage,
  ChatParams,
  PlanStep,
  PlanEvent,
  StepEvent,
  ToolEvent,
  SSEEventType,
  SSEEventData,
  SSEEventHandler,
  SessionFile,
  ViewFileParams,
  ViewShellParams,
} from "./types";

// 认证类型
export type {
  AuthUser,
  AuthTenant,
  AuthData,
  MeData,
  RegisterParams,
  LoginParams,
} from "./auth";

// 模块 API
export { authApi } from "./auth";
export { configApi } from "./config";
export { fileApi } from "./file";
export { sessionApi } from "./session";

