
from abc import ABC, abstractmethod
from typing import TypeVar

from .file_repository import FileRepository
from .membership_repository import MembershipRepository
from .session_repository import SessionRepository
from .tenant_repository import TenantRepository
from .user_repository import UserRepository

T = TypeVar("T", bound="IUnitOfWork")


class IUnitOfWork(ABC):
    """Uow模式协议接口"""
    file: FileRepository
    session: SessionRepository
    user: UserRepository
    tenant: TenantRepository
    membership: MembershipRepository

    @abstractmethod
    async def commit(self):
        """提交数据库数据持久化"""
        ...

    @abstractmethod
    async def flush(self):
        """将挂起的变更下发到数据库(不提交事务)，用于在同一事务内确保父行先于子行写入"""
        ...

    @abstractmethod
    async def rollback(self):
        """数据库回滚"""
        ...

    @abstractmethod
    async def __aenter__(self: T) -> T:
        """进入上下文管理器"""
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        ...
