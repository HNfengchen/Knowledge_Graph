from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from kg_system.core.models import SubgraphResult


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
    pool_wrapper.__aenter__ = AsyncMock(return_value=pool_wrapper)
    return pool_wrapper


@pytest.fixture
def ext_app(fake_redis):
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)
    from kg_system.api.v1.external import router as ext_router

    _app.include_router(ext_router, prefix="/api/v1")

    from kg_system.api.deps import get_redis

    _app.dependency_overrides[get_redis] = lambda: fake_redis

    _app.state.neo4j = None
    _app.state.redis = None
    _app.state.collector = None
    return _app


@pytest.fixture
async def ext_client(ext_app) -> AsyncClient:
    transport = ASGITransport(app=ext_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _ext_headers() -> dict:
    return {"X-API-Key": "test-external-key", "X-Forwarded-For": "127.0.0.1"}


# ── Auth ──


@pytest.mark.unit
class TestExternalAuth:
    async def test_missing_api_key(self, ext_client):
        resp = await ext_client.post(
            "/api/v1/kg/external/subgraph",
            json={"entity_name": "test"},
        )
        assert resp.status_code == 401

    async def test_wrong_api_key(self, ext_client):
        resp = await ext_client.post(
            "/api/v1/kg/external/subgraph",
            json={"entity_name": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401


# ── Rate Limit ──


@pytest.mark.unit
class TestExternalRateLimit:
    async def test_rate_limit_exceeded(self, ext_client, fake_redis):
        fake_redis.get_client().incr.return_value = 1000
        resp = await ext_client.post(
            "/api/v1/kg/external/subgraph",
            json={"entity_name": "test"},
            headers=_ext_headers(),
        )
        assert resp.status_code == 429


# ── Subgraph ──


@pytest.mark.unit
class TestSubgraphEndpoint:
    async def test_success(self, ext_client):
        mock_result = SubgraphResult(
            nodes=[{"id": "1", "name": "test", "type": "Entity", "props": {}}],
            links=[],
        )
        with patch("kg_system.api.v1.external.KGQueryService") as mock_kg_cls:
            mock_kg = AsyncMock()
            mock_kg_cls.return_value = mock_kg
            mock_kg.query_subgraph = AsyncMock(return_value=mock_result)

            resp = await ext_client.post(
                "/api/v1/kg/external/subgraph",
                json={"entity_name": "test", "depth": 2},
                headers=_ext_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["nodes"][0]["name"] == "test"
        assert data["data"]["nodes"][0]["type"] == "Entity"

    async def test_cache_hit(self, ext_client, fake_redis):
        cached = SubgraphResult(
            nodes=[{"id": "1", "name": "cached-entity", "type": "Entity", "props": {}}],
            links=[],
        )
        fake_redis.get_client().get.return_value = cached.model_dump_json().encode()

        with patch("kg_system.api.v1.external.KGQueryService") as mock_kg_cls:
            mock_kg = AsyncMock()
            mock_kg_cls.return_value = mock_kg

            resp = await ext_client.post(
                "/api/v1/kg/external/subgraph",
                json={"entity_name": "test", "depth": 2},
                headers=_ext_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["nodes"][0]["name"] == "cached-entity"
        mock_kg.query_subgraph.assert_not_called()

    async def test_cache_miss_sets_cache(self, ext_client, fake_redis):
        mock_result = SubgraphResult(
            nodes=[{"id": "1", "name": "test", "type": "Entity", "props": {}}],
            links=[],
        )
        with patch("kg_system.api.v1.external.KGQueryService") as mock_kg_cls:
            mock_kg = AsyncMock()
            mock_kg_cls.return_value = mock_kg
            mock_kg.query_subgraph = AsyncMock(return_value=mock_result)

            resp = await ext_client.post(
                "/api/v1/kg/external/subgraph",
                json={"entity_name": "test", "depth": 2},
                headers=_ext_headers(),
            )
        assert resp.status_code == 200
        fake_redis.get_client().setex.assert_called_once()


# ── Context ──


@pytest.mark.unit
class TestContextEndpoint:
    async def test_success(self, ext_client):
        mock_context = [{"name": "neighbor1", "relation": "RELATED_TO"}]
        mock_sg = SubgraphResult(
            nodes=[{"id": "1", "name": "test", "type": "Entity", "props": {}}],
            links=[],
        )
        with (
            patch("kg_system.api.v1.external.KGQueryService") as mock_kg_cls,
            patch("kg_system.api.v1.external.get_chat_model") as mock_get_chat,
        ):
            mock_kg = AsyncMock()
            mock_kg_cls.return_value = mock_kg
            mock_kg.get_entity_context = AsyncMock(return_value=mock_context)
            mock_kg.query_subgraph = AsyncMock(return_value=mock_sg)

            mock_llm = AsyncMock()
            mock_get_chat.return_value = mock_llm
            mock_msg = MagicMock()
            mock_msg.content = "围绕 test 的摘要"
            mock_llm.ainvoke = AsyncMock(return_value=mock_msg)

            resp = await ext_client.post(
                "/api/v1/kg/external/context",
                json={"entity_name": "test"},
                headers=_ext_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["summary"] == "围绕 test 的摘要"
        assert data["data"]["neighbors"] == mock_context
        assert "evidence" in data["data"]
        assert data["data"]["evidence"]["nodes"][0]["name"] == "test"


# ── Cypher ──


@pytest.mark.unit
class TestCypherEndpoint:
    @pytest.fixture
    def _override_neo4j(self, ext_app):
        from kg_system.api.deps import get_neo4j

        fake_neo4j = AsyncMock()
        fake_neo4j.execute_cypher = AsyncMock(return_value=[{"n": {"name": "test-result"}}])
        ext_app.dependency_overrides[get_neo4j] = lambda: fake_neo4j
        yield fake_neo4j
        ext_app.dependency_overrides.pop(get_neo4j, None)

    async def test_success(self, ext_client, _override_neo4j):
        resp = await ext_client.post(
            "/api/v1/kg/external/cypher",
            json={"cypher": "MATCH (n) RETURN n LIMIT 10", "params": {}},
            headers=_ext_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"] == [{"n": {"name": "test-result"}}]

    async def test_write_keyword_blocked(self, ext_client):
        resp = await ext_client.post(
            "/api/v1/kg/external/cypher",
            json={"cypher": "CREATE (n:Test {name: 'evil'})", "params": {}},
            headers=_ext_headers(),
        )
        # code=2003 is outside valid HTTP range, so status falls back to 500
        assert resp.status_code == 500
        data = resp.json()
        assert data["code"] == 2003

    async def test_timeout(self, ext_client, _override_neo4j):
        _override_neo4j.execute_cypher = AsyncMock(side_effect=asyncio.TimeoutError)

        resp = await ext_client.post(
            "/api/v1/kg/external/cypher",
            json={"cypher": "MATCH (n) RETURN n LIMIT 10", "params": {}},
            headers=_ext_headers(),
        )
        assert resp.status_code == 504

    async def test_auto_append_limit(self, ext_client, _override_neo4j):
        resp = await ext_client.post(
            "/api/v1/kg/external/cypher",
            json={"cypher": "MATCH (n) RETURN n", "params": {}},
            headers=_ext_headers(),
        )
        assert resp.status_code == 200
        called_cypher = _override_neo4j.execute_cypher.call_args[0][0]
        assert called_cypher.endswith("LIMIT 1000")

    async def test_delete_keyword_blocked(self, ext_client):
        resp = await ext_client.post(
            "/api/v1/kg/external/cypher",
            json={"cypher": "MATCH (n) DETACH DELETE n", "params": {}},
            headers=_ext_headers(),
        )
        assert resp.status_code == 500
        data = resp.json()
        assert data["code"] == 2003


# ── Embed ──


@pytest.mark.unit
class TestEmbedEndpoint:
    async def test_success(self, ext_client):
        mock_embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        with patch("kg_system.api.v1.external.get_embedding_model") as mock_get_emb:
            mock_model = AsyncMock()
            mock_get_emb.return_value = mock_model
            mock_model.aembed_documents = AsyncMock(return_value=mock_embeddings)

            resp = await ext_client.post(
                "/api/v1/kg/external/embed",
                json={"texts": ["hello world", "foo bar"]},
                headers=_ext_headers(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"] == mock_embeddings

    async def test_too_many_texts(self, ext_client):
        texts = ["x"] * 65
        resp = await ext_client.post(
            "/api/v1/kg/external/embed",
            json={"texts": texts},
            headers=_ext_headers(),
        )
        assert resp.status_code == 400

    async def test_single_text_too_long(self, ext_client):
        resp = await ext_client.post(
            "/api/v1/kg/external/embed",
            json={"texts": ["a" * 8001]},
            headers=_ext_headers(),
        )
        assert resp.status_code == 400

    async def test_model_unavailable(self, ext_client):
        with patch("kg_system.api.v1.external.get_embedding_model") as mock_get_emb:
            mock_get_emb.side_effect = Exception("embedding service down")

            resp = await ext_client.post(
                "/api/v1/kg/external/embed",
                json={"texts": ["hello"]},
                headers=_ext_headers(),
            )
        assert resp.status_code == 502
