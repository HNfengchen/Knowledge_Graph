# Streaming LLM — Design Spec

## Motivation

Add a token-level streaming endpoint that pushes LangGraph execution events (node transitions, LLM tokens, final answer) as Server-Sent Events.

## Scope

- New endpoint `POST /api/v1/reason/ask-stream` returning `text/event-stream`
- SSE helper module `reasoning/streaming.py`
- Uses LangGraph `astream_events` API (version "v2")

## Architecture

```
Client SSE ← StreamingResponse ← event_stream() generator ← graph.astream_events()
```

## Components

### `reasoning/streaming.py`

```python
def sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"

async def build_event_stream(graph: CompiledStateGraph, initial_state: dict) -> AsyncGenerator[str, None]:
    """Iterate astream_events and yield SSE-formatted strings."""
```

### Event Types

| event_type | data fields | When |
|-----------|-------------|------|
| `node_start` | `{node: str}` | On chain start for retrieve/reason/generate/decide |
| `token` | `{content: str}` | On chat model stream chunk |
| `node_end` | `{node: str}` | On chain end for named nodes |
| `complete` | `{answer, trace, evidence}` | Final state, one event |
| `error` | `{message}` | On any exception |

### `api/v1/reason.py` — new endpoint

```python
@router.post("/ask-stream")
async def ask_stream(body: AskRequest, ...) -> StreamingResponse:
    graph = _get_or_build_graph(...)
    initial_state = {...}
    return StreamingResponse(
        build_event_stream(graph, initial_state),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

## Non-goals

- WebSocket (SSE is sufficient for one-directional streaming)
- Cancellation support (can be added later via asyncio task cancel)
- Backpressure handling (FastAPI's StreamingResponse handles this)
