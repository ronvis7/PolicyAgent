from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PolicyManus后端中控配置信息，从.env或者环境变量中加载数据"""

    # 项目基础配置
    env: str = "development"
    log_level: str = "INFO"
    app_config_filepath: str = "config.yaml"

    # 数据库相关配置
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="policy_manus", alias="POSTGRES_DB")

    @property
    def sqlalchemy_database_uri(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Embedding(向量化)机密配置
    # base_url/model_name/dimension 等运营参数在 config.yaml 的 embed_config 中维护，
    # 此处仅承载机密 api_key，经 .env 注入，不入库。
    embed_api_key: str = Field(default="", alias="EMBED_API_KEY")

    # Redis缓存配置
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")

    # Cos腾讯云对象存储配置
    cos_secret_id: str = Field(default="", alias="COS_SECRET_ID")
    cos_secret_key: str = Field(default="", alias="COS_SECRET_KEY")
    cos_region: str = Field(default="", alias="COS_REGION")
    cos_scheme: str = Field(default="https", alias="COS_SCHEME")
    cos_bucket: str = Field(default="", alias="COS_BUCKET")
    cos_domain: str = Field(default="", alias="COS_DOMAIN")

    # Sandbox配置
    sandbox_address: Optional[str] = Field(default=None, alias="SANDBOX_ADDRESS")
    sandbox_image: Optional[str] = Field(default=None, alias="SANDBOX_IMAGE")
    sandbox_name_prefix: Optional[str] = Field(default=None, alias="SANDBOX_NAME_PREFIX")
    sandbox_ttl_minutes: Optional[int] = Field(default=60, alias="SANDBOX_TTL_MINUTES")
    sandbox_network: Optional[str] = Field(default=None, alias="SANDBOX_NETWORK")
    sandbox_chrome_args: Optional[str] = Field(default="", alias="SANDBOX_CHROME_ARGS")
    sandbox_https_proxy: Optional[str] = Field(default=None, alias="SANDBOX_HTTPS_PROXY")
    sandbox_http_proxy: Optional[str] = Field(default=None, alias="SANDBOX_HTTP_PROXY")
    sandbox_no_proxy: Optional[str] = Field(default=None, alias="SANDBOX_NO_PROXY")

    # 公开政策定时重爬配置（主线⑤：保鲜申报通知的申报截止日期）
    # 应用内调度器在 api 进程内按 cron 触发 ingest，复用进程内 DB/Embedding/LLM 连接。
    # 默认每天 04:00（错开备份 cron 03:30）重爬项目申报通知源 wnd-apply、上海杨浦区政府文件 shyp。
    policy_recrawl_enabled: bool = Field(default=True, alias="POLICY_RECRAWL_ENABLED")
    policy_recrawl_sources: str = Field(default="wnd-apply,shyp", alias="POLICY_RECRAWL_SOURCES")  # 逗号分隔
    policy_recrawl_hour: int = Field(default=4, alias="POLICY_RECRAWL_HOUR")
    policy_recrawl_minute: int = Field(default=0, alias="POLICY_RECRAWL_MINUTE")
    policy_recrawl_max_pages: int = Field(default=3, alias="POLICY_RECRAWL_MAX_PAGES")
    # 触发时区：默认按数据源所在地(无锡)的北京时间解释 hour，避免容器 UTC 下 04:00 实跑成中午。
    policy_recrawl_timezone: str = Field(default="Asia/Shanghai", alias="POLICY_RECRAWL_TIMEZONE")

    @property
    def policy_recrawl_source_list(self) -> list[str]:
        """解析逗号分隔的重爬来源为去空白的非空列表。"""
        return [s.strip() for s in self.policy_recrawl_sources.split(",") if s.strip()]

    # JWT认证配置
    jwt_secret_key: str = Field(default="dev-insecure-secret-change-me-in-production-please", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=14, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # 使用pydantic v2的写法来完成环境变量信息的告知
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """获取当前PolicyManus项目的配置信息，并对内容进行缓存，避免重复读取"""
    settings = Settings()
    return settings
