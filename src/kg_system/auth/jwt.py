from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from kg_system.core.config import get_settings
from kg_system.core.exceptions import AuthError


def create_access_token(sub: str, role: str = "user", ttl_seconds: int | None = None) -> str:
    s = get_settings()
    ttl = ttl_seconds or s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
    }
    return jwt.encode(payload, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def create_refresh_token(sub: str, jti: str | None = None, ttl_seconds: int | None = None) -> str:
    s = get_settings()
    ttl = ttl_seconds or 604800  # 7 天
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": "refresh",
        "jti": jti or uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
    }
    return jwt.encode(payload, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise AuthError(f"invalid token: {e}")
