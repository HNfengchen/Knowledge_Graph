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
def require_user(authorization: str | None = Header(default=None)) -> dict:
    """业务端点：Bearer JWT。骨架阶段只校验 token 非空 + 签名。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    token = authorization.split(None, 1)[1].strip()
    if not token:
        raise AuthError("empty bearer token")
    s = get_settings()
    try:
        from jose import jwt

        payload = jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    except Exception as e:
        raise AuthError(f"invalid token: {e}") from e
    return payload


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """管理端点：admin token 直接比对 settings.ADMIN_TOKEN。"""
    s = get_settings()
    if not s.ADMIN_TOKEN:
        raise AuthError("admin token not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing admin bearer token")
    token = authorization.split(None, 1)[1].strip()
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
