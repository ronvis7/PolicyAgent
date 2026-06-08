from typing import Protocol, Dict, Any


class TokenService(Protocol):
    """JWT令牌服务协议，封装access/refresh令牌的签发与解析"""

    def create_access_token(self, user_id: str, tenant_id: str, role: str) -> str:
        """签发短期access令牌，携带用户id、当前激活租户id与角色"""
        ...

    def create_refresh_token(self, user_id: str, tenant_id: str) -> str:
        """签发长期refresh令牌(内含唯一jti，用于Redis白名单与轮换)"""
        ...

    def decode(self, token: str) -> Dict[str, Any]:
        """解析并校验令牌(签名+过期)，返回claims；无效时抛出UnauthorizedError"""
        ...
