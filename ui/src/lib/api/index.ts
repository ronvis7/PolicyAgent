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
  RegisterMode,
  OrgOption,
  ListOrgsData,
  LoginParams,
} from "./auth";

// 知识库类型
export type {
  FileStatus,
  KnowledgeBase,
  KnowledgeFile,
  CreateKnowledgeBaseParams,
} from "./knowledge";

// 成员管理类型
export type {
  MembershipRole,
  MemberItem,
  ListMembersData,
  AddMemberParams,
} from "./membership";

// 企业档案类型
export type {
  EnterpriseScale,
  EnterpriseProfile,
  UpdateEnterpriseProfileParams,
} from "./profile";

// 公开政策库类型
export type {
  PolicyListItem,
  PolicyDetail,
  PolicyListResponse,
  ListPoliciesParams,
  PolicyMatchItem,
  PolicyMatchResponse,
  PolicySourceItem,
  PolicySourceListResponse,
} from "./policy";

// 工作台 Feed 类型（④）
export type {
  FeedStatus,
  SettableFeedStatus,
  FeedItem,
  FeedListResponse,
  ListFeedParams,
  RecomputeResult,
} from "./feed";

// 资质申报机会类型（⑥）
export type {
  QualificationLevel,
  QualificationMatchItem,
  QualificationMatchListResponse,
  QualificationDetail,
} from "./qualification";
export { QUALIFICATION_LEVEL_LABEL } from "./qualification";

// 模块 API
export { authApi } from "./auth";
export { configApi } from "./config";
export { fileApi } from "./file";
export { sessionApi } from "./session";
export { knowledgeApi, isFileProcessing, isFileFailed } from "./knowledge";
export { membershipApi } from "./membership";
export { profileApi } from "./profile";
export { policyApi } from "./policy";
export { feedApi } from "./feed";
export { qualificationApi } from "./qualification";

