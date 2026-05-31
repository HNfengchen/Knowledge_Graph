from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.unit
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert data["msg"] == "success"
    assert data["data"]["status"] == "ok"


@pytest.mark.unit
async def test_404_returns_envelope(client: AsyncClient):
    resp = await client.get("/nonexistent")
    assert resp.status_code == 404


@pytest.mark.unit
async def test_request_id_in_response(client: AsyncClient):
    resp = await client.get("/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0


@pytest.mark.unit
async def test_request_id_passthrough(client: AsyncClient):
    resp = await client.get("/health", headers={"X-Request-ID": "my-rid-123"})
    assert resp.headers["X-Request-ID"] == "my-rid-123"
