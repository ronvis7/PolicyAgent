from typing import Protocol


class PasswordHasher(Protocol):
    """密码哈希协议，封装密码的哈希与校验"""

    def hash(self, password: str) -> str:
        """对明文密码进行哈希，返回哈希串"""
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """校验明文密码与哈希串是否匹配"""
        ...
