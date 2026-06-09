from __future__ import annotations

import hashlib
import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from kg_system.api.deps import get_redis, get_user_repo, require_user
from kg_system.auth.jwt import create_access_token, create_refresh_token, decode_token
from kg_system.core.config import get_settings
from kg_system.core.exceptions import AuthError, RateLimitError
from kg_system.core.logging import get_logger
from kg_system.core.models import ApiResponse
from kg_system.storage.redis_client import RedisClient
from kg_system.storage.user_repo import UserRepo

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginReq(BaseModel):
    username: str
    password: str


class TokenReq(BaseModel):
    refresh_token: str


class LogoutReq(BaseModel):
    jti: str = ""


async def _check_login_rate_limit(redis: RedisClient, ip: str) -> None:
    minute = int(time.time()) // 60
    key = f"{get_settings().REDIS_KEY_PREFIX}auth:fail:{ip}:{minute}"
    r = redis.get_client()
    try:
        count = await r.get(key)
        if count and int(count) >= 5:
            raise RateLimitError("too many login attempts, try again later")
    finally:
        await r.close()


@router.post("/login", response_model=ApiResponse[dict])
async def login(
    body: LoginReq,
    request: Request,
    redis: RedisClient = Depends(get_redis),
    users: UserRepo = Depends(get_user_repo),
):
    ip = request.client.host if request.client else "unknown"
    await _check_login_rate_limit(redis, ip)

    user = await users.get_user(body.username)
    if not user:
        raise AuthError("invalid username or password")

    pw_hash = hashlib.sha256(body.password.encode()).hexdigest()
    if user["password_hash"] != pw_hash:
        r = redis.get_client()
        try:
            minute = int(time.time()) // 60
            key = f"{get_settings().REDIS_KEY_PREFIX}auth:fail:{ip}:{minute}"
            await r.incr(key)
            await r.expire(key, 60)
        finally:
            await r.close()
        raise AuthError("invalid username or password")

    access = create_access_token(body.username, role=user["role"])
    refresh = create_refresh_token(body.username)
    s = get_settings()

    return ApiResponse(
        data={
            "access_token": access,
            "refresh_token": refresh,
            "expires_in": s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@router.post("/refresh", response_model=ApiResponse[dict])
async def refresh_token(
    body: TokenReq,
    redis: RedisClient = Depends(get_redis),
    users: UserRepo = Depends(get_user_repo),
):
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise AuthError("invalid refresh token")

    jti = payload.get("jti", "")
    r = redis.get_client()
    try:
        revoked = await r.get(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{jti}")
        if revoked:
            raise AuthError("token revoked")
        await r.setex(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{jti}", 604800, "1")
    finally:
        await r.close()

    sub = payload.get("sub", "")
    user = await users.get_user(sub)
    role = user["role"] if user else "user"
    access = create_access_token(sub, role=role)
    new_refresh = create_refresh_token(sub)

    return ApiResponse(
        data={
            "access_token": access,
            "refresh_token": new_refresh,
            "expires_in": 900,
        }
    )


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    body: LogoutReq,
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    if body.jti:
        r = redis.get_client()
        try:
            await r.setex(f"{get_settings().REDIS_KEY_PREFIX}auth:revoked:{body.jti}", 604800, "1")
        finally:
            await r.close()

    return ApiResponse(data={"message": "logged out"})


@router.post("/register", response_model=ApiResponse[dict])
async def register(
    body: LoginReq,
    users: UserRepo = Depends(get_user_repo),
):
    if len(body.password) < 6:
        raise AuthError("password too short, minimum 6 characters")

    exists = await users.user_exists(body.username)
    if exists:
        raise AuthError("username already exists")

    pw_hash = hashlib.sha256(body.password.encode()).hexdigest()
    await users.create_user(body.username, pw_hash, role="user")
    return ApiResponse(data={"message": "user created"})
