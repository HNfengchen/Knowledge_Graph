from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt


def _bearer_token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": "test"}, "test-secret-key-for-testing-only", algorithm="HS256"
    )


async def _fake_events():
    yield {
        "event": "on_chain_start",
        "name": "retrieve_node",
        "data": {},
    }
    yield {
        "event": "on_chain_end",
        "name": "retrieve_node",
        "data": {"output": {"next_action": "reason"}},
    }
    yield {
        "event": "on_chain_start",
        "name": "reason_node",
        "data": {},
    }
    yield {
        "event": "on_chat_model_stream",
        "data": {"chunk": MagicMock(content="hello ")},
    }
    yield {
        "event": "on_chat_model_stream",
        "data": {"chunk": MagicMock(content="world")},
    }
    yield {
        "event": "on_chain_end",
        "name": "reason_node",
        "data": {"output": {"next_action": "generate", "reasoning_trace": ["thought"]}},
    }
    yield {
        "event": "on_chain_start",
        "name": "generate_node",
        "data": {},
    }
    yield {
        "event": "on_chain_end",
        "name": "generate_node",
        "data": {
            "output": {
                "next_action": "end",
                "answer": "final answer",
                "reasoning_trace": ["thought", "generated"],
                "subgraph": '{"nodes": [], "links": []}',
            }
        },
    }


@pytest.fixture
def stream_app():
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)

    @_app.get("/health", response_model=dict)
    async def health():
        return {"status": "ok"}

    from kg_system.api.v1.reason import router as reason_router
    _app.include_router(reason_router, prefix="/api/v1")

    _app.state.neo4j = None
    _app.state.redis = None
    _app.state.collector = None
    return _app


@pytest.mark.unit
async def test_ask_stream_returns_sse(stream_app):
    with patch("kg_system.api.v1.reason._get_or_build_graph") as mock_builder:
        mock_graph = MagicMock()
        mock_graph.astream_events.return_value = _fake_events()
        mock_builder.return_value = mock_graph

        transport = ASGITransport(app=stream_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/reason/ask-stream",
                json={"question": "test", "max_steps": 3},
                headers={"Authorization": _bearer_token()},
            )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    import json
    lines = resp.text.strip().split("\n\n")
    events = [json.loads(l.replace("data: ", "")) for l in lines if l.startswith("data:")]
    types = [e["type"] for e in events]

    assert "node_start" in types
    assert "token" in types
    assert "complete" in types


@pytest.mark.unit
async def test_ask_stream_question_too_long(stream_app):
    transport = ASGITransport(app=stream_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/reason/ask-stream",
            json={"question": "x" * 6000, "max_steps": 3},
            headers={"Authorization": _bearer_token()},
        )
    assert resp.status_code == 400
