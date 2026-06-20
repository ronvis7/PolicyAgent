import asyncio
import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.logging import setup_logging
from app.infrastructure.scheduler.briefing_refresh_scheduler import BriefingRefreshScheduler
from app.infrastructure.scheduler.policy_recrawl_scheduler import PolicyRecrawlScheduler
from app.infrastructure.storage.cos import get_cos
from app.infrastructure.storage.postgres import get_postgres
from app.infrastructure.storage.redis import get_redis
from app.interfaces.endpoints.routes import router
from app.interfaces.errors.exception_handlers import register_exception_handlers
from app.interfaces.service_dependencies import get_default_agent_service, get_policy_ingest_service, get_briefing_service
from core.config import get_settings


# 1.加载配置信息
settings = get_settings()

# 2.初始化日志系统
setup_logging()
logger = logging.getLogger()


openapi_tags = [
    {
        "name": "状态模块",
        "description": "包含 **状态监测** 等api接口，用于监测系统的运行状态。",
    }
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """创建FastAPI应用生命周期上下文管理器"""
    # 0.重新初始化日志系统(uvicorn启动时dictConfig会影响根日志处理器，需要在此重新配置)
    setup_logging()

    # 1.日志打印代码已经开始执行了
    logger.info("PolicyManus正在初始化")

    # 2.运行数据库迁移(将数据同步到生产环境)
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    # 3.初始化Redis/Postgres/Cos客户端
    await get_redis().init()
    await get_postgres().init()
    await get_cos().init()

    # 3.5 启动公开政策定时重爬调度器(主线⑤；DB 初始化后再起，任务依赖 uow)
    recrawl_scheduler: PolicyRecrawlScheduler | None = None
    if settings.policy_recrawl_enabled:
        recrawl_scheduler = PolicyRecrawlScheduler(
            sources=settings.policy_recrawl_source_list,
            hour=settings.policy_recrawl_hour,
            minute=settings.policy_recrawl_minute,
            max_pages=settings.policy_recrawl_max_pages,
            ingest=lambda source, max_pages: get_policy_ingest_service().ingest(source, max_pages),
            timezone=settings.policy_recrawl_timezone,
        )
        recrawl_scheduler.start()
    else:
        logger.info("公开政策定时重爬已禁用(POLICY_RECRAWL_ENABLED=false)")

    # 3.6 启动主动情报简报定时重算调度器(主动情报 Agent；错开 04:00 重爬、基于最新政策生成)
    briefing_scheduler: BriefingRefreshScheduler | None = None
    if settings.briefing_refresh_enabled:
        briefing_scheduler = BriefingRefreshScheduler(
            hour=settings.briefing_refresh_hour,
            minute=settings.briefing_refresh_minute,
            regenerate_all=lambda: get_briefing_service().regenerate_all(),
            timezone=settings.briefing_refresh_timezone,
        )
        briefing_scheduler.start()
    else:
        logger.info("主动情报简报定时重算已禁用(BRIEFING_REFRESH_ENABLED=false)")

    try:
        # 4.lifespan分界点
        yield
    finally:
        # 4.5 停止调度器
        if recrawl_scheduler is not None:
            recrawl_scheduler.shutdown()
        if briefing_scheduler is not None:
            briefing_scheduler.shutdown()

        try:
            # 5.等待agent服务关闭
            logger.info("PolicyManus正在关闭")
            await asyncio.wait_for(get_default_agent_service().shutdown(), timeout=30.0)
            logger.info("Agent服务成功关闭")
        except asyncio.TimeoutError:
            logger.warning("Agent服务关闭超时, 强制关闭, 部分任务将被释放")
        except Exception as e:
            logger.error(f"Agent服务关闭期间出现错误: {str(e)}")

        # 6.关闭其他应用
        await get_redis().shutdown()
        await get_postgres().shutdown()
        await get_cos().shutdown()

        logger.info("PolicyManus应用关闭成功")


# 4.创建PolicyManus FastAPI应用程序实例
app = FastAPI(
    title="PolicyManus 企业政策咨询智能体",
    description="PolicyManus 是面向企业的政策咨询 AI Agent，支持政策检索、解读、匹配与报告生成，并可通过 A2A、MCP 和沙箱工具扩展能力。",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
    version="1.0.0",
)

# 5.配置CORS中间件解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6.注册异常处理
register_exception_handlers(app)

# 7.集成路由
app.include_router(router, prefix="/api")


