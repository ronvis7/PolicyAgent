from typing import Protocol, Optional

from app.domain.models.user import User


class UserRepository(Protocol):
    """用户仓库协议定义"""

    async def save(self, user: User) -> None:
        """存储或更新用户"""
        ...

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """根据用户id查询用户"""
        ...

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查询用户"""
        ...
