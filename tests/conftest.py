from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from fastapi import Request
from kg_system.core.config import get_settings
from kg_system.core.models import ApiResponse
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.postgres_client import PostgresClient
from kg_system.storage.redis_client import RedisClient


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """所有测试使用最小 env 配置，避免依赖真实外部服务。"""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:17687")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "16379")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("EXTERNAL_API_KEY", "test-external-key")
    monkeypatch.setenv("EXTERNAL_API_IP_WHITELIST", "127.0.0.1,::1,testclient")
    monkeypatch.setenv("LOG_FORMAT", "console")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()


@pytest.fixture
def app():
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)

    @_app.get("/health", response_model=ApiResponse[dict])
    async def health() -> ApiResponse[dict]:
        return ApiResponse(data={"status": "ok"})

    @_app.get("/health/ready", response_model=ApiResponse[dict])
    async def health_ready(request: Request) -> ApiResponse[dict]:
        state = request.app.state
        statuses: dict[str, str] = {}

        neo4j: Neo4jClient | None = getattr(state, "neo4j", None)
        if neo4j:
            try:
                await neo4j.execute_cypher("RETURN 1 AS ok")
                statuses["neo4j"] = "ok"
            except Exception:
                statuses["neo4j"] = "unavailable"
        else:
            statuses["neo4j"] = "not_configured"

        redis: RedisClient | None = getattr(state, "redis", None)
        if redis:
            try:
                r = redis.get_client()
                await r.ping()
                await r.close()
                statuses["redis"] = "ok"
            except Exception:
                statuses["redis"] = "unavailable"
        else:
            statuses["redis"] = "not_configured"

        postgres: PostgresClient | None = getattr(state, "postgres", None)
        if postgres:
            try:
                await postgres.fetchrow("SELECT 1 AS ok")
                statuses["postgres"] = "ok"
            except Exception:
                statuses["postgres"] = "unavailable"
        else:
            statuses["postgres"] = "not_configured"

        all_ok = all(v == "ok" for v in statuses.values())
        if not all_ok:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content=ApiResponse(code=503, msg="not ready", data=statuses).model_dump(),
            )
        return ApiResponse(data=statuses)

    from kg_system.api.v1.kg import router as kg_router
    from kg_system.api.v1.reason import router as reason_router
    from kg_system.api.v1.analysis import router as analysis_router
    from kg_system.api.v1.external import router as external_router

    _app.include_router(kg_router, prefix="/api/v1")
    _app.include_router(reason_router, prefix="/api/v1")
    _app.include_router(analysis_router, prefix="/api/v1")
    _app.include_router(external_router, prefix="/api/v1")

    _app.state.neo4j = None
    _app.state.redis = None
    _app.state.collector = None
    return _app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
