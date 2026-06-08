from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import User
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.models import UserModel


class DBUserRepository(UserRepository):
    """基于Postgres数据库的用户仓库"""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, user: User) -> None:
        """新增或更新用户"""
        # 1.根据id查询用户是否存在
        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # 2.不存在则新建，存在则更新
        if not record:
            self.db_session.add(UserModel.from_domain(user))
            return
        record.update_from_domain(user)

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """根据用户id查询用户"""
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查询用户"""
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.to_domain() if record is not None else None
