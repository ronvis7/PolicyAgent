
import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.domain.repositories.uow import IUnitOfWork
from .db_document_chunk_repository import DBDocumentChunkRepository
from .db_file_repository import DBFileRepository
from .db_knowledge_base_repository import DBKnowledgeBaseRepository
from .db_knowledge_file_repository import DBKnowledgeFileRepository
from .db_membership_repository import DBMembershipRepository
from .db_session_repository import DBSessionRepository
from .db_tenant_repository import DBTenantRepository
from .db_user_repository import DBUserRepository

logger = logging.getLogger(__name__)


class DBUnitOfWork(IUnitOfWork):
    """基于Postgres数据库的UoW实例"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """构造函数，完成UoW类初始化"""
        self.session_factory = session_factory
        self.db_session: Optional[AsyncSession] = None

    async def commit(self):
        """提交数据库持久化"""
        await self.db_session.commit()

    async def flush(self):
        """将挂起的变更下发到数据库(不提交事务)

        会话配置了autoflush=False，且ORM模型间未声明relationship，
        因此跨表的父子行(如user/tenant与membership)在同一次commit的flush中
        排序不可靠，可能子行先insert而违反外键约束。在保存子行前显式flush
        父行可确保写入顺序正确。
        """
        await self.db_session.flush()

    async def rollback(self):
        """数据库回退操作"""
        await self.db_session.rollback()

    async def __aenter__(self) -> "DBUnitOfWork":
        """进入UoW操作上下文管理器的逻辑"""
        # 1.为每个上下文开启一个新的会话
        self.db_session = self.session_factory()

        # 2.初始化所有数据库仓库
        self.file = DBFileRepository(db_session=self.db_session)
        self.session = DBSessionRepository(db_session=self.db_session)
        self.user = DBUserRepository(db_session=self.db_session)
        self.tenant = DBTenantRepository(db_session=self.db_session)
        self.membership = DBMembershipRepository(db_session=self.db_session)
        self.knowledge_base = DBKnowledgeBaseRepository(db_session=self.db_session)
        self.knowledge_file = DBKnowledgeFileRepository(db_session=self.db_session)
        self.document_chunk = DBDocumentChunkRepository(db_session=self.db_session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时执行的逻辑，如果出现异常则回滚，否则提交

        当SSE客户端断开连接时，sse_starlette的cancel scope会取消所有await操作，
        包括此处的commit/rollback/close。如果不妥善处理CancelledError，
        会导致连接池中的连接处于异常状态，影响后续使用该池的其他任务。
        """
        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        except asyncio.CancelledError:
            # SSE断连等场景下cancel scope取消了commit/rollback操作，
            # 记录警告但不让异常传播，避免后续close操作也被跳过
            logger.warning("UoW提交/回滚操作被取消(可能是客户端断开连接)")
        except Exception as e:
            logger.error(f"UoW提交/回滚操作失败: {e}")
            # 提交失败必须向上抛出，否则会向客户端返回"成功"却未持久化数据；
            # 若已在回滚(exc_type存在)，则不再覆盖触发回滚的原始异常
            if exc_type is None:
                raise
        finally:
            try:
                await self.db_session.close()
            except asyncio.CancelledError:
                logger.warning("UoW关闭数据库会话被取消(可能是客户端断开连接)")
            except Exception as e:
                logger.warning(f"UoW关闭数据库会话失败: {e}")
