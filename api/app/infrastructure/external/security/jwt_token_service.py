import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from jwt import InvalidTokenError

from app.application.errors.exceptions import UnauthorizedError
from app.domain.external.token_service import TokenService

logger = logging.getLogger(__name__)

# 令牌类型标识
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class JWTTokenService(TokenService):
    """基于PyJWT的令牌服务实现"""

    def __init__(
            self,
            secret_key: str,
            algorithm: str,
            access_token_expire_minutes: int,
            refresh_token_expire_days: int,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_token_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_token_expire_days)

    def create_access_token(self, user_id: str, tenant_id: str, role: str) -> str:
        """签发access令牌，携带用户、激活租户与角色"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "tid": tenant_id,
            "role": role,
            "type": TOKEN_TYPE_ACCESS,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + self._access_expire,
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: str, tenant_id: str) -> str:
        """签发refresh令牌(含唯一jti，配合Redis白名单做轮换/吊销)"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "tid": tenant_id,
            "type": TOKEN_TYPE_REFRESH,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + self._refresh_expire,
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode(self, token: str) -> Dict[str, Any]:
        """解析并校验令牌，无效或过期抛出UnauthorizedError"""
        try:
            return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except InvalidTokenError as e:
            logger.warning(f"令牌校验失败: {str(e)}")
            raise UnauthorizedError("登录状态已失效，请重新登录")
