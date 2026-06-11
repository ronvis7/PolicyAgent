import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.agent_service import AgentService
from app.application.services.app_config_service import AppConfigService
from app.application.services.auth_service import AuthService
from app.application.services.file_service import FileService
from app.application.services.knowledge_service import KnowledgeService
from app.application.services.session_service import SessionService
from app.application.services.status_service import StatusService
from app.domain.external.password_hasher import PasswordHasher
from app.domain.external.token_service import TokenService
from app.infrastructure.external.security.argon2_password_hasher import Argon2Hasher
from app.infrastructure.external.security.jwt_token_service import JWTTokenService
from app.infrastructure.external.file_storage.cos_file_storage import CosFileStorage
from app.infrastructure.external.health_checker.postgres_health_checker import PostgresHealthChecker
from app.infrastructure.external.health_checker.redis_health_checker import RedisHealthChecker
from app.infrastructure.external.json_parser.repair_json_parser import RepairJSONParser
from app.infrastructure.external.document_parser.pymupdf_parser import PyMuPDFParser
from app.infrastructure.external.embedding.openai_embedding import OpenAIEmbedding
from app.infrastructure.external.llm.openai_llm import OpenAILLM
from app.infrastructure.external.sandbox.docker_sandbox import DockerSandbox
from app.infrastructure.external.search.bing_search import BingSearchEngine
from app.infrastructure.external.task.redis_stream_task import RedisStreamTask
from app.infrastructure.repositories.file_app_config_repository import FileAppConfigRepository
from app.infrastructure.storage.cos import Cos, get_cos
from app.infrastructure.storage.postgres import get_db_session, get_uow
from app.infrastructure.storage.redis import RedisClient, get_redis
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_app_config_service() -> AppConfigService:
    """获取应用配置服务"""
    # 1.获取数据仓库并打印日志
    logger.info("加载获取AppConfigService")
    file_app_config_repository = FileAppConfigRepository(settings.app_config_filepath)

    # 2.实例化AppConfigService
    return AppConfigService(app_config_repository=file_app_config_repository)


def get_status_service(
        db_session: AsyncSession = Depends(get_db_session),
        redis_client: RedisClient = Depends(get_redis),
) -> StatusService:
    """获取状态服务"""
    # 1.初始化postgres和redis健康检查
    postgres_checker = PostgresHealthChecker(db_session)
    redis_checker = RedisHealthChecker(redis_client)

    # 2.创建服务并返回
    logger.info("加载获取StatusService")
    return StatusService(checkers=[postgres_checker, redis_checker])


def get_file_service(
        cos: Cos = Depends(get_cos)
) -> FileService:
    # 1.初始化文件仓库和文件存储桶
    file_storage = CosFileStorage(
        bucket=settings.cos_bucket,
        cos=cos,
        uow_factory=get_uow,
    )

    # 2.构建服务并返回
    return FileService(
        uow_factory=get_uow,
        file_storage=file_storage,
    )

def get_knowledge_service(
        cos: Cos = Depends(get_cos),
) -> KnowledgeService:
    """获取知识库服务(含 COS 文件存储 + Embedding + 文档解析)"""
    # 1. 实时读取应用配置(embed_config 的 base_url/model/dimension)
    app_config = FileAppConfigRepository(config_path=settings.app_config_filepath).load()

    # 2. 构建依赖：COS 文件存储 + Embedding 提供商(api_key 来自 .env) + 解析器
    file_storage = CosFileStorage(
        bucket=settings.cos_bucket,
        cos=cos,
        uow_factory=get_uow,
    )
    embedding = OpenAIEmbedding(app_config.embed_config, api_key=settings.embed_api_key)

    # 3. 构建知识库服务并返回
    return KnowledgeService(
        uow_factory=get_uow,
        file_storage=file_storage,
        embedding=embedding,
        parser=PyMuPDFParser(),
    )


def get_session_service() -> SessionService:
    return SessionService(uow_factory=get_uow, sandbox_cls=DockerSandbox)


def get_password_hasher() -> PasswordHasher:
    """获取密码哈希器"""
    return Argon2Hasher()


def get_token_service() -> TokenService:
    """获取JWT令牌服务"""
    return JWTTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
    )


def get_auth_service(
        redis_client: RedisClient = Depends(get_redis),
) -> AuthService:
    """获取认证服务"""
    return AuthService(
        uow_factory=get_uow,
        password_hasher=get_password_hasher(),
        token_service=get_token_service(),
        redis_client=redis_client,
        refresh_token_ttl_seconds=settings.refresh_token_expire_days * 24 * 3600,
    )


def get_agent_service(
        cos: Cos = Depends(get_cos),
) -> AgentService:
    # 1.获取应用配置信息(读取配置需要实时获取,所以不配置缓存)
    app_config_repository = FileAppConfigRepository(config_path=settings.app_config_filepath)
    app_config = app_config_repository.load()

    # 2.构建依赖实例
    llm = OpenAILLM(app_config.llm_config)
    file_storage = CosFileStorage(
        bucket=settings.cos_bucket,
        cos=cos,
        uow_factory=get_uow,
    )

    # 3.实例Agent服务并返回
    return AgentService(
        uow_factory=get_uow,
        llm=llm,
        agent_config=app_config.agent_config,
        mcp_config=app_config.mcp_config,
        a2a_config=app_config.a2a_config,
        sandbox_cls=DockerSandbox,
        task_cls=RedisStreamTask,
        json_parser=RepairJSONParser(),
        search_engine=BingSearchEngine(),
        file_storage=file_storage,
    )