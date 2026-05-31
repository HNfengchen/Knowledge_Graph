from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kg_system.api.deps import get_kg_query, get_neo4j, get_redis, require_user
from kg_system.core.config import get_settings
from kg_system.core.exceptions import InvalidInput, LLMError
from kg_system.core.models import ApiResponse, SubgraphResult
from kg_system.kg_query.service import KGQueryService
from kg_system.llm.callbacks import AnalysisCallbackHandler
from kg_system.llm.factory import get_chat_model
from kg_system.reasoning.graph import build_reasoning_graph
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.redis_client import RedisClient

router = APIRouter(prefix="/reason", tags=["reason"])


class AskRequest(BaseModel):
    question: str
    max_steps: int = Field(5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    reasoning_trace: list[str]
    evidence: SubgraphResult


_graph_cache: dict = {}


def _get_or_build_graph(neo4j: Neo4jClient, redis: RedisClient):
    key = "reasoning_graph"
    if key not in _graph_cache:
        callback = AnalysisCallbackHandler(redis)
        llm = get_chat_model().with_config({"callbacks": [callback]})
        kg_service = KGQueryService(neo4j)
        _graph_cache[key] = build_reasoning_graph(llm, kg_service)
    return _graph_cache[key]


@router.post("/ask", response_model=ApiResponse[AskResponse])
async def ask_endpoint(
    body: AskRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    s = get_settings()
    if len(body.question) > (s.TEXT_MAX_LENGTH // 2):
        raise InvalidInput(f"question too long, max {s.TEXT_MAX_LENGTH // 2}")

    graph = _get_or_build_graph(neo4j, redis)

    initial_state = {
        "question": body.question,
        "max_steps": body.max_steps,
        "step_count": 0,
        "reasoning_trace": [],
        "subgraph": None,
        "next_action": "retrieve",
        "answer": "",
    }

    import asyncio

    try:
        final_state = await asyncio.wait_for(
            graph.ainvoke(initial_state),
            timeout=s.OPENAI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        from kg_system.core.exceptions import LLMTimeoutError

        raise LLMTimeoutError("reasoning timed out")
    except Exception as e:
        raise LLMError(f"reasoning failed: {e}") from e

    subgraph_data = final_state.get("subgraph", "{}")
    if isinstance(subgraph_data, str):
        try:
            subgraph_dict = json.loads(subgraph_data)
        except (json.JSONDecodeError, TypeError):
            subgraph_dict = {"nodes": [], "links": []}
    elif isinstance(subgraph_data, dict):
        subgraph_dict = subgraph_data
    else:
        subgraph_dict = {"nodes": [], "links": []}

    evidence = SubgraphResult(
        nodes=subgraph_dict.get("nodes", []),
        links=subgraph_dict.get("links", []),
    )

    return ApiResponse(
        data=AskResponse(
            answer=final_state.get("answer", ""),
            reasoning_trace=final_state.get("reasoning_trace", []),
            evidence=evidence,
        )
    )
