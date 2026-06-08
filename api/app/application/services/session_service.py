

import logging
from typing import List, Callable, Type

from app.application.errors.exceptions import NotFoundError, ServerRequestsError
from app.domain.external.sandbox import Sandbox
from app.domain.models.file import File
from app.domain.models.session import Session
from app.domain.repositories.uow import IUnitOfWork
from app.interfaces.schemas.session import FileReadResponse, ShellReadResponse

logger = logging.getLogger(__name__)


class SessionService:
    """会话服务"""

    def __init__(
            self,
            uow_factory: Callable[[], IUnitOfWork],
            sandbox_cls: Type[Sandbox],
    ) -> None:
        """构造函数，完成会话服务初始化"""
        self._uow_factory = uow_factory
        self._uow = uow_factory()
        self._sandbox_cls = sandbox_cls

    async def create_session(self, tenant_id: str, owner_id: str) -> Session:
        """创建一个空白的新任务会话(归属指定租户与创建者)"""
        logger.info(f"租户[{tenant_id}]创建一个空白新任务会话")
        session = Session(title="新对话", tenant_id=tenant_id, owner_id=owner_id)
        async with self._uow:
            await self._uow.session.save(session)
        logger.info(f"成功创建一个新任务会话: {session.id}")
        return session

    async def get_all_sessions(self, tenant_id: str) -> List[Session]:
        """获取指定租户下的所有任务会话列表"""
        async with self._uow:
            return await self._uow.session.get_all(tenant_id=tenant_id)

    async def ensure_access(self, session_id: str, tenant_id: str) -> Session:
        """校验会话归属当前租户，存在则返回，否则抛出NotFound(隔离核心)"""
        async with self._uow:
            session = await self._uow.session.get_by_id(session_id, tenant_id=tenant_id)
        if not session:
            raise NotFoundError(f"会话[{session_id}]不存在，请核实后重试")
        return session

    async def clear_unread_message_count(self, session_id: str, tenant_id: str) -> None:
        """清空指定会话未读消息数(校验租户归属)"""
        logger.info(f"清除会话[{session_id}]未读消息数")
        await self.ensure_access(session_id, tenant_id)
        async with self._uow:
            await self._uow.session.update_unread_message_count(session_id, 0)

    async def delete_session(self, session_id: str, tenant_id: str) -> None:
        """根据传递的会话id删除任务会话(校验租户归属)"""
        # 1.先校验会话归属当前租户
        logger.info(f"正在删除会话, 会话id: {session_id}")
        await self.ensure_access(session_id, tenant_id)

        # 2.按租户作用域删除会话
        async with self._uow:
            await self._uow.session.delete_by_id(session_id, tenant_id=tenant_id)
        logger.info(f"删除会话[{session_id}]成功")

    async def get_session(self, session_id: str, tenant_id: str) -> Session:
        """获取指定会话详情信息(校验租户归属)"""
        async with self._uow:
            return await self._uow.session.get_by_id(session_id, tenant_id=tenant_id)

    async def get_session_files(self, session_id: str, tenant_id: str) -> List[File]:
        """根据传递的会话id获取指定会话的文件列表信息(校验租户归属)"""
        logger.info(f"获取指定会话[{session_id}]下的文件列表信息")
        session = await self.ensure_access(session_id, tenant_id)
        return session.files

    async def read_file(self, session_id: str, tenant_id: str, filepath: str) -> FileReadResponse:
        """根据传递的信息查看会话中指定文件的内容(校验租户归属)"""
        # 1.校验会话归属当前租户
        logger.info(f"获取会话[{session_id}]中的文件内容, 文件路径: {filepath}")
        session = await self.ensure_access(session_id, tenant_id)

        # 2.根据沙箱id获取沙箱并判断是否存在
        if not session.sandbox_id:
            raise NotFoundError("当前会话无沙箱环境")
        sandbox = await self._sandbox_cls.get(session.sandbox_id)
        if not sandbox:
            raise NotFoundError("当前会话沙箱不存在或已销毁")

        # 3.调用沙箱读取文件内容
        result = await sandbox.read_file(filepath)
        if result.success:
            return FileReadResponse(**result.data)

        raise ServerRequestsError(result.message)

    async def read_shell_output(self, session_id: str, tenant_id: str, shell_session_id: str) -> ShellReadResponse:
        """根据传递的任务会话id+Shell会话id获取Shell执行结果(校验租户归属)"""
        # 1.校验会话归属当前租户
        logger.info(f"获取会话[{session_id}]中的Shell内容输出, Shell标识符: {shell_session_id}")
        session = await self.ensure_access(session_id, tenant_id)

        # 2.根据沙箱id获取沙箱并判断是否存在
        if not session.sandbox_id:
            raise NotFoundError("当前会话无沙箱环境")
        sandbox = await self._sandbox_cls.get(session.sandbox_id)
        if not sandbox:
            raise NotFoundError("当前会话沙箱不存在或已销毁")

        # 3.调用沙箱查看shell内容
        result = await sandbox.read_shell_output(session_id=shell_session_id, console=True)
        if result.success:
            return ShellReadResponse(**result.data)

        raise ServerRequestsError(result.message)

    async def get_vnc_url(self, session_id: str, tenant_id: str) -> str:
        """获取指定会话的vnc链接(校验租户归属)"""
        # 1.校验会话归属当前租户
        logger.info(f"获取会话[{session_id}]的VNC链接")
        session = await self.ensure_access(session_id, tenant_id)

        # 2.根据沙箱id获取沙箱并判断是否存在
        if not session.sandbox_id:
            raise NotFoundError("当前会话无沙箱环境")
        sandbox = await self._sandbox_cls.get(session.sandbox_id)
        if not sandbox:
            raise NotFoundError("当前会话沙箱不存在或已销毁")

        return sandbox.vnc_url
