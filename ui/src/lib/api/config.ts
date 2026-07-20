import { get, post } from "./fetch";
import type {
  LLMConfig,
  EmbedConfig,
  FeishuConfig,
  ContestSearchConfig,
  AgentConfig,
  MCPConfig,
  MCPServersData,
  A2AServersData,
  CreateA2AServerParams,
} from "./types";

/**
 * 配置模块 API
 */
export const configApi = {
  /**
   * 获取 LLM 配置
   */
  getLLMConfig: (): Promise<LLMConfig> => {
    return get<LLMConfig>("/app-config/llm");
  },

  /**
   * 更新 LLM 配置
   */
  updateLLMConfig: (config: LLMConfig): Promise<LLMConfig> => {
    const payload = {
      base_url: config.base_url,
      api_key: config.api_key ?? "",
      model_name: config.model_name,
      temperature: config.temperature,
      max_tokens: config.max_tokens,
    };
    return post<LLMConfig>("/app-config/llm", payload);
  },

  /**
   * 获取 Embedding 配置（双轨私有侧；base_url/model/dimension 为平台锁定值）
   */
  getEmbedConfig: (): Promise<EmbedConfig> => {
    return get<EmbedConfig>("/app-config/embedding");
  },

  /**
   * 更新组织 Embedding 密钥（租户只能配 api_key，留空表示不修改）
   */
  updateEmbedConfig: (apiKey: string): Promise<EmbedConfig> => {
    return post<EmbedConfig>("/app-config/embedding", { api_key: apiKey ?? "" });
  },

  /** 获取当前组织赛事搜索配置（不回显密钥） */
  getContestSearchConfig: (): Promise<ContestSearchConfig> => {
    return get<ContestSearchConfig>("/app-config/contest-search");
  },

  /** 保存/轮换当前组织百度千帆搜索密钥；留空表示不修改 */
  updateContestSearchConfig: (apiKey: string): Promise<ContestSearchConfig> => {
    return post<ContestSearchConfig>("/app-config/contest-search", {api_key: apiKey ?? ""});
  },

  /**
   * 获取组织飞书推送配置（脱敏回显）
   */
  getFeishuConfig: (): Promise<FeishuConfig> => {
    return get<FeishuConfig>("/app-config/feishu");
  },

  /**
   * 更新组织飞书推送配置（secret 留空表示不修改已有签名密钥）
   */
  updateFeishuConfig: (webhookUrl: string, secret: string): Promise<FeishuConfig> => {
    return post<FeishuConfig>("/app-config/feishu", {
      webhook_url: webhookUrl ?? "",
      secret: secret ?? "",
    });
  },

  /**
   * 清除组织飞书推送配置（停用新赛事推送）
   */
  clearFeishuConfig: (): Promise<FeishuConfig> => {
    return post<FeishuConfig>("/app-config/feishu/delete", {});
  },

  /**
   * 发送飞书测试消息（用已保存的配置）
   */
  testFeishuPush: (): Promise<FeishuConfig> => {
    return post<FeishuConfig>("/app-config/feishu/test", {});
  },

  /**
   * 获取 Agent 通用配置
   */
  getAgentConfig: (): Promise<AgentConfig> => {
    return get<AgentConfig>("/app-config/agent");
  },

  /**
   * 更新 Agent 通用配置
   */
  updateAgentConfig: (config: AgentConfig): Promise<AgentConfig> => {
    return post<AgentConfig>("/app-config/agent", config);
  },

  /**
   * 获取 MCP 服务器列表
   */
  getMCPServers: (): Promise<MCPServersData> => {
    return get<MCPServersData>("/app-config/mcp-servers");
  },

  /**
   * 新增 MCP 服务配置
   * @param config MCP 配置对象，格式为 { mcpServers: { [serverName]: MCPServerConfig } }
   */
  addMCPServer: (config: MCPConfig): Promise<void> => {
    return post<void>("/app-config/mcp-servers", config);
  },

  /**
   * 删除 MCP 服务
   */
  deleteMCPServer: (serverName: string): Promise<void> => {
    return post<void>(`/app-config/mcp-servers/${serverName}/delete`, {});
  },

  /**
   * 更新 MCP 启用状态
   */
  updateMCPServerEnabled: (
    serverName: string,
    enabled: boolean
  ): Promise<void> => {
    return post<void>(
      `/app-config/mcp-servers/${serverName}/enabled`,
      { enabled }
    );
  },

  /**
   * 获取 A2A 服务器列表
   */
  getA2AServers: (): Promise<A2AServersData> => {
    return get<A2AServersData>("/app-config/a2a-servers");
  },

  /**
   * 新增 A2A 服务器
   * @param params 包含 base_url 的请求参数
   */
  addA2AServer: (params: CreateA2AServerParams): Promise<void> => {
    return post<void>("/app-config/a2a-servers", params);
  },

  /**
   * 删除 A2A 服务
   */
  deleteA2AServer: (a2aId: string): Promise<void> => {
    return post<void>(`/app-config/a2a-servers/${a2aId}/delete`, {});
  },

  /**
   * 更新 A2A 启用状态
   */
  updateA2AServerEnabled: (
    a2aId: string,
    enabled: boolean
  ): Promise<void> => {
    return post<void>(
      `/app-config/a2a-servers/${a2aId}/enabled`,
      { enabled }
    );
  },
};
