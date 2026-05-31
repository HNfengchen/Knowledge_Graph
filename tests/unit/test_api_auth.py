from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from kg_system.core.models import ApiResponse


@pytest.fixture
def fake_user_repo():
    repo = AsyncMock()
    repo.get_user.return_value = {
        "username": "alice",
        "password_hash": hashlib.sha256("secret".encode()).hexdigest(),
        "role": "user",
    }
    repo.user_exists.return_value = False
    repo.create_user.return_value = {
        "username": "bob",
        "password_hash": "xxx",
        "role": "user",
    }
    return repo


@pytest.fixture
def fake_redis():
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=None)
    fake_client.setex = AsyncMock(return_value=True)
    fake_client.incr = AsyncMock(return_value=1)
    fake_client.expire = AsyncMock(return_value=True)
    fake_client.close = AsyncMock(return_value=None)

    pool_wrapper = AsyncMock()
    pool_wrapper.get_client = MagicMock(return_value=fake_client)
    return pool_wrapper


@pytest.fixture
def auth_app(fake_user_repo, fake_redis):
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)

    @_app.get("/health", response_model=ApiResponse[dict])
    async def health() -> ApiResponse[dict]:
        return ApiResponse(data={"status": "ok"})

    from kg_system.api.v1.auth import router as auth_router
    from kg_system.api.v1.kg import router as kg_router

    _app.include_router(auth_router, prefix="/api/v1")
    _app.include_router(kg_router, prefix="/api/v1")

    from kg_system.api.deps import get_redis, get_user_repo

    _app.dependency_overrides[get_user_repo] = lambda: fake_user_repo
    _app.dependency_overrides[get_redis] = lambda: fake_redis

    _app.state.neo4j = None
    _app.state.redis = None
    _app.state.collector = None
    return _app


@pytest.fixture
async def auth_client(auth_app) -> AsyncGenerator[AsyncClient, Any]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.unit
class TestAuthLogin:
    async def test_login_success(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "access_token" in data["data"]

    async def test_login_wrong_password(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_user(self, auth_client, fake_user_repo):
        fake_user_repo.get_user.return_value = None
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "x"},
        )
        assert resp.status_code == 401


@pytest.mark.unit
class TestAuthRegister:
    async def test_register_success(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "bob", "password": "pass123"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    async def test_register_duplicate(self, auth_client, fake_user_repo):
        fake_user_repo.user_exists.return_value = True
        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "bob", "password": "pass123"},
        )
        assert resp.status_code == 401

    async def test_register_password_too_short(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "bob", "password": "12345"},
        )
        assert resp.status_code == 401
        assert "6" in resp.json()["msg"]
