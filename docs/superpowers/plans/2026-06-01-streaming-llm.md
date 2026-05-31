# Streaming LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a token-level streaming endpoint `POST /api/v1/reason/ask-stream` using LangGraph's `astream_events` + SSE.

**Architecture:** SSE helper in `reasoning/streaming.py` yields `data: {json}\n\n` events from `graph.astream_events()`. The FastAPI endpoint wraps it in `StreamingResponse`.

**Tech Stack:** LangGraph astream_events (v2), FastAPI StreamingResponse, SSE

---

### Task 1: Create streaming helper module

**Files:**
- Create: `src/kg_system/reasoning/streaming.py`
- Create: `tests/unit/test_reasoning_streaming.py`

- [ ] **Create `src/kg_system/reasoning/streaming.py`**

```python
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph.graph import CompiledGraph

from kg_system.core.models import SubgraphResult
from kg_system.reasoning.state import ReasonerState


def sse_event(event_type: str, **kwargs: Any) -> str:
    payload = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def build_event_stream(
    graph: CompiledGraph,
    initial_state: ReasonerState,
) -> AsyncGenerator[str, None]:
    NODE_EVENTS = {"retrieve_node", "reason_node", "generate_node", "decide_node"}

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event["event"]
            node = event.get("name", "")

            if kind == "on_chain_start" and node in NODE_EVENTS:
                yield sse_event("node_start", node=node)

            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = getattr(chunk, "content", "")
                if content:
                    yield sse_event("token", content=content)

            elif kind == "on_chain_end" and node in NODE_EVENTS:
                output = event["data"].get("output", {})
                if isinstance(output, dict) and output.get("next_action") == "end":
                    answer = output.get("answer", "")
                    trace = output.get("reasoning_trace", [])
                    subgraph_str = output.get("subgraph", "{}")
                    if isinstance(subgraph_str, str):
                        try:
                            subgraph_dict = json.loads(subgraph_str)
                        except (json.JSONDecodeError, TypeError):
                            subgraph_dict = {"nodes": [], "links": []}
                    else:
                        subgraph_dict = subgraph_str
                    evidence = SubgraphResult(
                        nodes=subgraph_dict.get("nodes", []),
                        links=subgraph_dict.get("links", []),
                    )
                    yield sse_event("complete", answer=answer, trace=trace, evidence=evidence.model_dump())
                else:
                    yield sse_event("node_end", node=node)

    except Exception as e:
        yield sse_event("error", message=str(e))
```

- [ ] **Create `tests/unit/test_reasoning_streaming.py`**

```python
from __future__ import annotations

import json

import pytest

from kg_system.reasoning.streaming import sse_event


@pytest.mark.unit
class TestSseEvent:
    def test_basic_event(self):
        result = sse_event("node_start", node="retrieve")
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "node_start"
        assert data["node"] == "retrieve"

    def test_token_event(self):
        result = sse_event("token", content="hello")
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "token"
        assert data["content"] == "hello"

    def test_complete_event(self):
        result = sse_event("complete", answer="42", trace=["step1"], evidence={"nodes": []})
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "complete"
        assert data["answer"] == "42"
        assert data["trace"] == ["step1"]

    def test_error_event(self):
        result = sse_event("error", message="oops")
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "error"
        assert data["message"] == "oops"

    def test_format_ends_with_double_newline(self):
        result = sse_event("test", foo="bar")
        assert result.endswith("\n\n")
```

- [ ] **Run streaming module tests**

```bash
cd /mnt/e/projects/Knowledge_Graph && PYTHONPATH=src python -m pytest tests/unit/test_reasoning_streaming.py -m unit -v
```

Expected: 5 passed

- [ ] **Commit**

```bash
git add src/kg_system/reasoning/streaming.py tests/unit/test_reasoning_streaming.py
git commit -m "feat: add streaming SSE helper module"
```

---

### Task 2: Add /ask-stream endpoint

**Files:**
- Modify: `src/kg_system/api/v1/reason.py`
- Create: `tests/unit/test_reasoning_stream_endpoint.py`

- [ ] **Add imports and `/ask-stream` endpoint to `reason.py`**

Add these imports:
```python
from collections.abc import AsyncGenerator

from fastapi.responses import StreamingResponse

from kg_system.reasoning.streaming import build_event_stream
```

Add after the existing `ask_endpoint` function:

```python
@router.post("/ask-stream")
async def ask_stream(
    body: AskRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    s = get_settings()
    if len(body.question) > (s.TEXT_MAX_LENGTH // 2):
        from kg_system.core.exceptions import InvalidInput
        raise InvalidInput(f"question too long, max {s.TEXT_MAX_LENGTH // 2}")

    graph = _get_or_build_graph(neo4j, redis)

    initial_state: ReasonerState = {
        "question": body.question,
        "max_steps": body.max_steps,
        "step_count": 0,
        "reasoning_trace": [],
        "subgraph": None,
        "next_action": "retrieve",
        "answer": "",
    }

    return StreamingResponse(
        build_event_stream(graph, initial_state),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

Also add `ReasonerState` to the imports if it's not already imported (it isn't, add it):
```python
from kg_system.reasoning.state import ReasonerState
```

- [ ] **Create endpoint integration tests**

```python
# tests/unit/test_reasoning_stream_endpoint.py
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from kg_system.core.models import ApiResponse


@pytest.fixture
def stream_app():
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)

    @_app.get("/health", response_model=ApiResponse[dict])
    async def health() -> ApiResponse[dict]:
        return ApiResponse(data={"status": "ok"})

    from kg_system.api.v1.reason import router as reason_router
    _app.include_router(reason_router, prefix="/api/v1")

    _app.state.neo4j = None
    _app.state.redis = None
    _app.state.collector = None
    return _app


@pytest.fixture
def fake_graph():
    """Mock the reasoning graph to yield events without real LLM."""
    from langgraph.graph.graph import CompiledGraph

    g = MagicMock(spec=CompiledGraph)
    g.astream_events.return_value = _fake_events()
    return g


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


@pytest.mark.unit
async def test_ask_stream_returns_sse(stream_app):
    with patch("kg_system.api.v1.reason._get_or_build_graph") as mock_builder:
        mock_builder.return_value = MagicMock()
        mock_builder.return_value.astream_events.return_value = _fake_events()

        transport = ASGITransport(app=stream_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/reason/ask-stream",
                json={"question": "test", "max_steps": 3},
            )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream"

    lines = resp.text.strip().split("\n\n")
    assert len(lines) > 0

    import json
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
        )
    assert resp.status_code == 400
```

- [ ] **Run all tests**

```bash
cd /mnt/e/projects/Knowledge_Graph && PYTHONPATH=src python -m pytest tests/ -m unit --no-header --tb=short -v
```

Expected: 89 passed (82 original + 5 streaming + 2 stream endpoint)

- [ ] **Commit**

```bash
git add src/kg_system/api/v1/reason.py tests/unit/test_reasoning_stream_endpoint.py
git commit -m "feat: add /ask-stream streaming endpoint with SSE"
```
