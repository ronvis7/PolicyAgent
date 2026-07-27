

from typing import List

from pydantic import BaseModel, Field, HttpUrl

from app.domain.models.app_config import MCPTransport


class PublicLLMConfig(BaseModel):
    """可安全返回给前端的LLM配置，不包含密钥明文"""
    base_url: HttpUrl
    model_name: str
    temperature: float
    max_tokens: int
    api_key_configured: bool
    is_custom: bool = False  # 是否为当前组织自定义(False表示正在使用平台默认配置)


class PublicEmbedConfig(BaseModel):
    """可安全返回给前端的Embedding配置，不含密钥明文。

    双轨私有侧：base_url/model_name/dimension 为平台锁定值(只读展示)，租户仅可配 api_key。
    """
    base_url: HttpUrl
    model_name: str
    dimension: int
    api_key_configured: bool
    is_custom: bool = False  # 是否为当前组织自定义(False表示回落平台默认key)


class UpdateEmbedConfigRequest(BaseModel):
    """更新组织Embedding配置请求：租户只能配 api_key(其余锁平台)"""
    api_key: str = ""  # 为空表示不修改(沿用已有或回落平台默认)


class PublicContestSearchConfig(BaseModel):
    """赛事搜索公开配置，不包含密钥明文。"""
    provider: str = "baidu"
    api_key_configured: bool = False
    is_custom: bool = False
    fallback_enabled: bool = True


class UpdateContestSearchConfigRequest(BaseModel):
    """更新组织百度赛事搜索密钥；空值表示不修改。"""
    api_key: str = ""


class PublicFeishuConfig(BaseModel):
    """可安全返回给前端的飞书双通道配置。"""
    configured: bool = False  # 是否已配置(未配置=不推送)
    webhook_url_masked: str = ""  # 脱敏后的 webhook URL(仅保留尾部便于辨认)
    secret_configured: bool = False  # 是否配置了签名校验密钥
    app_configured: bool = False
    app_enabled: bool = False
    app_id_masked: str = ""
    app_secret_configured: bool = False
    verification_token_configured: bool = False
    encrypt_key_configured: bool = False
    chat_id_masked: str = ""
class UpdateFeishuConfigRequest(BaseModel):
    """更新组织飞书双通道配置；凭据空值表示保留已有。"""
    webhook_url: str = ""
    secret: str = ""
    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""
    chat_id: str = ""
    app_enabled: bool = False


class ListMCPServerItem(BaseModel):
    """MCP服务列表条目选项"""
    server_name: str = ""  # 服务名字
    enabled: bool = True  # 启用状态
    transport: MCPTransport = MCPTransport.STREAMABLE_HTTP  # 传输协议
    tools: List[str] = Field(default_factory=list)  # 工具名字列表


class ListMCPServerResponse(BaseModel):
    """获取MCP服务列表响应结构"""
    mcp_servers: List[ListMCPServerItem] = Field(default_factory=list)  # MCP服务列表

class ListA2AServerItem(BaseModel):
    """A2A服务列表条目选项"""
    id: str = ""  # id
    name: str = ""  # 名字
    description: str = ""  # 描述信息
    input_modes: List[str] = Field(default_factory=list)  # 输入模态
    output_modes: List[str] = Field(default_factory=list)  # 输出模态
    streaming: bool = False  # 是否支持流式
    push_notifications: bool = False  # 是否支持推送通知
    enabled: bool = True  # 启用状态


class ListA2AServerResponse(BaseModel):
    """获取A2A服务列表响应结构"""
    a2a_servers: List[ListA2AServerItem] = Field(default_factory=list)  # A2A服务列表
