from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from kg_system.core.models import SubgraphResult
from kg_system.reasoning.state import ReasonerState


def sse_event(event_type: str, **kwargs: Any) -> str:
    payload = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def build_event_stream(
    graph: CompiledStateGraph,
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
                        subgraph_dict = {"nodes": [], "links": []}
                    evidence = SubgraphResult(
                        nodes=subgraph_dict.get("nodes", []),
                        links=subgraph_dict.get("links", []),
                    )
                    yield sse_event("complete", answer=answer, trace=trace, evidence=evidence.model_dump())
                else:
                    yield sse_event("node_end", node=node)

    except Exception as e:
        yield sse_event("error", message=str(e))
