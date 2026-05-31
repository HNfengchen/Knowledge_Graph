from __future__ import annotations

from fastapi import Depends, Header, Request

from kg_system.core.config import get_settings
from kg_system.core.exceptions import AuthError
from kg_system.kg_query.service import KGQueryService
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.redis_client import RedisClient


# —— 资源依赖 —— #
def get_neo4j(request: Request) -> Neo4jClient:
    return request.app.state.neo4j


def get_redis(request: Request) -> RedisClient:
    return request.app.state.redis


def get_kg_query(neo4j: Neo4jClient = Depends(get_neo4j)) -> KGQueryService:
    return KGQueryService(neo4j)


# —— 认证依赖 —— #
def _decode_and_check(token: str) -> dict:
    from kg_system.auth.jwt import decode_token

    payload = decode_token(token)
    return payload


def require_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    """业务端点：Bearer JWT。校验签名 + 黑名单。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    parts = authorization.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        raise AuthError("empty bearer token")
    payload = _decode_and_check(parts[1].strip())

    # 检查 access token 是否在黑名单（redis 不可用则跳过）
    jti = payload.get("jti", "")
    if jti:
        try:
            redis = request.app.state.redis
            if redis:
                from kg_system.core.config import get_settings

                r = redis.get_client()
                try:
                    revoked = r.get(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{jti}")
                    if revoked:
                        raise AuthError("token revoked")
                finally:
                    r.close()
        except (AttributeError, Exception):
            pass

    request.state.user = payload
    return payload


def require_role(role: str):
    """角色守卫装饰器。"""

    def _checker(user: dict = Depends(require_user)) -> None:
        if user.get("role") != role:
            raise AuthError(f"requires {role} role")

    return _checker


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """管理端点：admin token 直接比对 settings.ADMIN_TOKEN。"""
    s = get_settings()
    if not s.ADMIN_TOKEN:
        raise AuthError("admin token not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing admin bearer token")
    parts = authorization.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        raise AuthError("missing admin bearer token")
    token = parts[1].strip()
    if token != s.ADMIN_TOKEN:
        raise AuthError("invalid admin token")


def require_external(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """外部接口：API Key + IP 白名单。"""
    s = get_settings()
    if not s.EXTERNAL_API_KEY:
        raise AuthError("external API key not configured")
    if x_api_key != s.EXTERNAL_API_KEY:
        raise AuthError("invalid external API key")
    client_host = request.client.host if request.client else ""
    if client_host not in s.external_ip_whitelist:
        raise AuthError(f"IP {client_host} not in whitelist")
