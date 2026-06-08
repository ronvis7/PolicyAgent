import logging

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.domain.external.password_hasher import PasswordHasher

logger = logging.getLogger(__name__)


class Argon2Hasher(PasswordHasher):
    """基于argon2-cffi的密码哈希实现"""

    def __init__(self) -> None:
        # 使用argon2id默认参数(已是业界推荐的安全默认值)
        self._hasher = Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        """对明文密码进行argon2id哈希"""
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """校验明文密码与哈希串是否匹配，不匹配返回False而非抛异常"""
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
