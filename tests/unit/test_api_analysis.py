from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def analyze_app():
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)

    from kg_system.api.v1.analysis import router as analysis_router
    _app.include_router(analysis_router, prefix="/api/v1")

    _app.state.redis = None
    _app.state.collector = None
    return _app


ADMIN_TOKEN = "test-admin-token"


@pytest.mark.unit
async def test_analyze_endpoint_success(analyze_app):
    with patch("kg_system.api.v1.analysis.MetricsAggregator") as MockAgg:
        mock_agg = AsyncMock()
        mock_agg.get_qps = AsyncMock(return_value=10.5)
        mock_agg.get_latency_percentiles = AsyncMock(return_value={"p50": 42.0, "p99": 150.0})
        mock_agg.get_error_rate = AsyncMock(return_value=0.02)
        mock_agg.get_daily_cost_usd = AsyncMock(return_value=1.25)
        MockAgg.return_value = mock_agg

        transport = ASGITransport(app=analyze_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/llm/analyze?window_seconds=300",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["qps"] == 10.5
    assert data["avg_latency_ms"] == 42.0
    assert data["p99_latency_ms"] == 150.0
    assert data["error_rate"] == 0.02
    assert data["daily_cost_usd"] == 1.25


@pytest.mark.unit
async def test_analyze_endpoint_no_auth(analyze_app):
    transport = ASGITransport(app=analyze_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/llm/analyze?window_seconds=300")

    assert resp.status_code == 401


@pytest.mark.unit
async def test_analyze_endpoint_requires_admin(analyze_app):
    transport = ASGITransport(app=analyze_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/llm/analyze?window_seconds=300",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert resp.status_code == 401
