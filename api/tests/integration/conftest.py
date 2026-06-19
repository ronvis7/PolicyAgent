"""DB-in-CI 集成测试基建：真 Postgres + pgvector + alembic + 真仓储。

与 `tests/app/isolation/`(内存仓储、测端点/服务作用域层)互补：本套件连**真库、跑真仓储**，
覆盖仓储 SQL 层的隔离 WHERE 回归(某仓储漏掉 tenant 过滤)——这是内存仓储测不到的那层。

仅在显式启用时运行：需 `RUN_DB_TESTS=1` + `POSTGRES_*` 指向一个可写的 Postgres(CI 用
service 容器，镜像 pgvector/pgvector:pg16)。未启用时本目录所有用例自动 skip，
不影响离线单元 job。
"""

import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.repositories.db_uow import DBUnitOfWork
from core.config import get_settings

# tests/integration/conftest.py → parents[2] = api 目录(alembic.ini 所在)
_API_DIR = Path(__file__).resolve().parents[2]
# 本目录(集成测试)，用于把 skip 严格限定在集成用例上
_THIS_DIR = Path(__file__).resolve().parent


def _enabled() -> bool:
    return os.getenv("RUN_DB_TESTS") == "1"


def pytest_collection_modifyitems(config, items):
    """未启用真库时，仅把**本目录**用例标记 skip(而非失败)。

    注意：conftest 的 hook 作用于整个会话，必须按路径过滤，否则会误伤其它离线测试。
    """
    if _enabled():
        return
    skip = pytest.mark.skip(
        reason="集成测试需真 Postgres：设 RUN_DB_TESTS=1 并提供 POSTGRES_* 连接",
    )
    for item in items:
        if _THIS_DIR in Path(str(item.fspath)).resolve().parents:
            item.add_marker(skip)


async def _prepare_extensions(uri: str) -> None:
    """建库扩展(pgvector/uuid-ossp)，迁移与运行时都依赖。"""
    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def _migrated_db():
    """全套件一次：建扩展 + alembic upgrade head(跑真实迁移链，连带验证迁移可用)。"""
    if not _enabled():
        yield
        return

    settings = get_settings()
    asyncio.run(_prepare_extensions(settings.sqlalchemy_database_uri))

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def uow_factory(_migrated_db):
    """返回真 DBUnitOfWork 工厂(NullPool：每次连接用后即关，避免跨 asyncio.run 复用)。"""
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_uri, poolclass=NullPool)
    session_factory = async_sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False,
    )

    def factory() -> DBUnitOfWork:
        return DBUnitOfWork(session_factory=session_factory)

    yield factory
    asyncio.run(engine.dispose())
