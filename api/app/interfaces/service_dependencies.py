import logging
from typing import List, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.errors.exceptions import UnauthorizedError
from app.application.services.agent_memory_service import AgentMemoryService
from app.application.services.agent_service import AgentService
from app.application.services.briefing_service import BriefingService
from app.application.services.app_config_service import AppConfigService
from app.application.services.auth_service import AuthService
from app.application.services.enterprise_profile_service import EnterpriseProfileService
from app.application.services.feed_service import FeedService
from app.application.services.report_service import ReportService
from app.application.services.file_service import FileService
from app.application.services.knowledge_service import KnowledgeService
from app.application.services.membership_service import MembershipService
from app.application.services.policy_ingest_service import PolicyIngestService
from app.application.services.policy_match_service import PolicyMatchService
from app.application.services.policy_service import PolicyService
from app.application.services.qualification_service import QualificationService
from app.application.services.session_service import SessionService
from app.application.services.status_service import StatusService
from app.application.services.tenant_settings_service import TenantSettingsService
from app.domain.models.app_config import LLMConfig
from app.domain.models.policy import Policy
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
from app.infrastructure.data.qualification_catalog import load_qualification_catalog
from app.infrastructure.external.crawler.registry import (
    build_crawlers,
    competition_source_keys,
    list_sources,
)
from app.infrastructure.external.notify.feishu_webhook import (
    FeishuWebhookNotifier,
    make_contest_push_hook,
    make_tenant_contest_push_hook,
)
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


def _build_agent_service(cos: Cos, app_config, llm_config: LLMConfig) -> AgentService:
    """用给定的 LLM 配置组装 AgentService(其余配置取平台级)"""
    llm = OpenAILLM(llm_config)
    file_storage = CosFileStorage(
        bucket=settings.cos_bucket,
        cos=cos,
        uow_factory=get_uow,
    )
    embedding = OpenAIEmbedding(app_config.embed_config, api_key=settings.embed_api_key)

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
        embedding=embedding,
        file_storage=file_storage,
        qualification_catalog=load_qualification_catalog(),
    )


# 可选 Bearer 鉴权方案(无凭据不报错)，用于在请求中按需解析租户上下文
_optional_bearer_scheme = HTTPBearer(auto_error=False)


async def _get_optional_tenant_id(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer_scheme),
        token_service: TokenService = Depends(get_token_service),
) -> Optional[str]:
    """从 access 令牌解析当前激活租户id；无凭据或令牌无效时返回 None。

    刻意定义在本模块(而非 auth_dependencies)，避免 service_dependencies 与
    auth_dependencies 互相导入形成循环。
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        claims = token_service.decode(credentials.credentials)
    except UnauthorizedError:
        return None
    if claims.get("type") != "access":
        return None
    return claims.get("tid")


async def get_knowledge_service(
        cos: Cos = Depends(get_cos),
        tenant_id: Optional[str] = Depends(_get_optional_tenant_id),
) -> KnowledgeService:
    """获取知识库服务(含 COS 文件存储 + Embedding + 文档解析)。

    Embedding 为双轨私有侧(见 ADR 003)：按当前登录租户解析——组织 BYO api_key 优先，
    回落平台 .env key；base_url/model/dimension 始终锁平台(维度恒 1024、同向量空间)。
    上传文件的后台向量化复用本次请求注入的 service，故按租户 key 计费。
    """
    # 1. 实时读取应用配置(embed_config 的 base_url/model/dimension)
    app_config_repository = FileAppConfigRepository(config_path=settings.app_config_filepath)

    # 2. 解析当前租户生效的 Embedding 配置；无租户上下文时用平台默认
    embed_config = app_config_repository.load().embed_config
    if tenant_id is not None:
        tenant_settings_service = TenantSettingsService(
            uow_factory=get_uow,
            app_config_repository=app_config_repository,
        )
        embed_config, _ = await tenant_settings_service.resolve_embed_config(tenant_id)
    # 组织未配 key 时 embed_config.api_key 为占位/空 → 回落平台 .env key
    api_key = embed_config.api_key.strip() or settings.embed_api_key

    # 3. 构建依赖：COS 文件存储 + Embedding 提供商 + 解析器
    file_storage = CosFileStorage(
        bucket=settings.cos_bucket,
        cos=cos,
        uow_factory=get_uow,
    )
    embedding = OpenAIEmbedding(embed_config, api_key=api_key)

    # 4. 构建知识库服务并返回
    return KnowledgeService(
        uow_factory=get_uow,
        file_storage=file_storage,
        embedding=embedding,
        parser=PyMuPDFParser(),
    )


async def get_agent_service(
        cos: Cos = Depends(get_cos),
        tenant_id: Optional[str] = Depends(_get_optional_tenant_id),
) -> AgentService:
    """获取 Agent 服务，LLM 配置按当前登录租户解析(组织自定义优先，回落平台默认)"""
    # 1.获取应用配置信息(读取配置需要实时获取,所以不配置缓存)
    app_config_repository = FileAppConfigRepository(config_path=settings.app_config_filepath)
    app_config = app_config_repository.load()

    # 2.解析当前租户生效的 LLM 配置；无租户上下文(如未认证)时用平台默认
    llm_config = app_config.llm_config
    if tenant_id is not None:
        tenant_settings_service = TenantSettingsService(
            uow_factory=get_uow,
            app_config_repository=app_config_repository,
        )
        llm_config = await tenant_settings_service.get_llm_config(tenant_id)

    # 3.组装并返回
    return _build_agent_service(cos, app_config, llm_config)


def get_default_agent_service() -> AgentService:
    """用平台默认 LLM 配置构造 Agent 服务，供无请求上下文的场景(如应用关闭)使用"""
    app_config_repository = FileAppConfigRepository(config_path=settings.app_config_filepath)
    app_config = app_config_repository.load()
    return _build_agent_service(get_cos(), app_config, app_config.llm_config)


def get_tenant_settings_service() -> TenantSettingsService:
    """获取租户设置服务(按租户读写 LLM 配置)"""
    app_config_repository = FileAppConfigRepository(config_path=settings.app_config_filepath)
    return TenantSettingsService(uow_factory=get_uow, app_config_repository=app_config_repository)


def get_membership_service() -> MembershipService:
    """获取组织成员管理服务"""
    return MembershipService(uow_factory=get_uow)


def get_enterprise_profile_service() -> EnterpriseProfileService:
    """获取企业档案服务(按租户读写结构化档案)"""
    return EnterpriseProfileService(uow_factory=get_uow)


def get_agent_memory_service() -> AgentMemoryService:
    """获取 Agent 长期记忆管理服务(按租户读/删跨会话记忆)"""
    return AgentMemoryService(uow_factory=get_uow)


def get_policy_service() -> PolicyService:
    """获取公开政策库读服务(全局共享，分页浏览)"""
    return PolicyService(uow_factory=get_uow)


def _build_contest_push_hook():
    """构造"新赛事即推"飞书回调，两级组合：

    - 租户级(主)：组织在设置页配置 webhook 后自动生效，按参赛关注地区过滤后扇出推送；
    - 部署级(兜底)：配置了 env FEISHU_WEBHOOK_URL 时额外全量推送到该群，不过滤。
    各级独立 best-effort，互不拖累。
    """
    contest_keys = competition_source_keys()
    contest_source_names = {
        s.key: s.name for s in list_sources() if s.key in contest_keys
    }
    hooks = [make_tenant_contest_push_hook(get_uow, contest_source_names)]
    if settings.feishu_webhook_url:
        notifier = FeishuWebhookNotifier(
            webhook_url=settings.feishu_webhook_url,
            secret=settings.feishu_webhook_secret,
        )
        hooks.append(make_contest_push_hook(notifier, contest_source_names))

    async def push_all(source: str, new_policies: List[Policy]) -> None:
        for hook in hooks:
            try:
                await hook(source, new_policies)
            except Exception as e:  # noqa: BLE001 — 单级失败不影响另一级
                logger.warning("新赛事推送回调失败: %s: %s", type(e).__name__, e)

    return push_all


def get_policy_ingest_service() -> PolicyIngestService:
    """获取公开政策入库编排服务(按来源选择爬虫 + 结构化 upsert + 向量双写 + 截止日期抽取)。

    抽取用平台默认 LLM(系统级入库无租户)；平台未配 key 时 OpenAILLM 会抛错，
    此处吞掉传 None，让入库照常进行(截止字段留 unknown)，与 best-effort 纪律一致。
    配置 FEISHU_WEBHOOK_URL 后，赛事子源入库的新增经飞书群机器人即推(best-effort)。
    """
    app_config = FileAppConfigRepository(config_path=settings.app_config_filepath).load()
    embedding = OpenAIEmbedding(app_config.embed_config, api_key=settings.embed_api_key)
    try:
        llm = OpenAILLM(app_config.llm_config)
    except Exception as e:  # noqa: BLE001 — 抽取为可选增强，缺 key 不应阻断②入库
        logger.warning("平台 LLM 未就绪，本次入库跳过截止日期抽取: %s", e)
        llm = None
    return PolicyIngestService(
        uow_factory=get_uow,
        crawlers=build_crawlers(),
        embedding=embedding,
        llm=llm,
        on_new_policies=_build_contest_push_hook(),
        skip_expired_sources=competition_source_keys(),
    )


def get_policy_match_service() -> PolicyMatchService:
    """获取政策匹配服务(③：企业档案 × 公开政策，结构化+语义融合)"""
    app_config = FileAppConfigRepository(config_path=settings.app_config_filepath).load()
    embedding = OpenAIEmbedding(app_config.embed_config, api_key=settings.embed_api_key)
    return PolicyMatchService(uow_factory=get_uow, embedding=embedding)


def get_qualification_service() -> QualificationService:
    """获取资质机会服务(⑥：企业档案 × 资质目录启发式匹配 + 详情读取)"""
    return QualificationService(uow_factory=get_uow, catalog=load_qualification_catalog())


def get_feed_service() -> FeedService:
    """获取工作台 Feed 服务(④：物化③政策/赛事 + ⑥资质匹配结果 + 状态机)"""
    return FeedService(
        uow_factory=get_uow,
        match_service=get_policy_match_service(),
        qualification_service=get_qualification_service(),
        competition_sources=competition_source_keys(),
    )


def get_report_service() -> ReportService:
    """获取政策匹配简报组装服务（主线尾巴：复用档案/Feed/资质服务组装 PDF 简报）。"""
    return ReportService(
        profile_service=get_enterprise_profile_service(),
        feed_service=get_feed_service(),
        qualification_service=get_qualification_service(),
    )


def get_briefing_service() -> BriefingService:
    """获取主动情报简报服务（复用 ReportService 聚合 + 平台默认 LLM 归纳）。

    简报用平台默认 LLM(系统级生成无租户)；平台未配 key 时吞掉传 None，
    服务自动回退确定性兜底简报，与 best-effort 纪律一致。
    """
    app_config = FileAppConfigRepository(config_path=settings.app_config_filepath).load()
    try:
        llm = OpenAILLM(app_config.llm_config)
    except Exception as e:  # noqa: BLE001 — 简报为增强，缺 key 走兜底而非报错
        logger.warning("平台 LLM 未就绪，情报简报将走确定性兜底: %s", e)
        llm = None
    return BriefingService(
        uow_factory=get_uow,
        report_service=get_report_service(),
        llm=llm,
    )