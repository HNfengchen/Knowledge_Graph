from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from kg_system.api.deps import get_kg_query, get_neo4j, get_redis, require_external
from kg_system.core.config import get_settings
from kg_system.core.exceptions import InvalidInput, RateLimitError, RequestTimeout
from kg_system.core.models import ApiResponse, SubgraphResult
from kg_system.kg_query.service import KGQueryService
from kg_system.llm.factory import get_chat_model, get_embedding_model
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.redis_client import RedisClient

router = APIRouter(prefix="/kg/external", tags=["external"])

_WRITE_KEYWORDS = re.compile(
    r"\b(create|merge|delete|detach|set|remove|drop|load\s+csv|call\s+db\.\w*\.*write)\b",
    re.I,
)


class SubgraphReq(BaseModel):
    entity_name: str
    depth: int = Field(2, ge=1, le=3)
    relation_types: list[str] | None = None


class ContextReq(BaseModel):
    entity_name: str
    max_neighbors: int = Field(10, ge=1, le=100)


class CypherReq(BaseModel):
    cypher: str
    params: dict = Field(default_factory=dict)


class EmbedReq(BaseModel):
    texts: list[str]


async def _check_rate_limit(request: Request, redis: RedisClient) -> None:
    s = get_settings()
    api_key = request.headers.get(s.API_KEY_HEADER, "unknown")
    minute = int(time.time()) // 60
    key = f"{s.REDIS_KEY_PREFIX}rl:{api_key}:{minute}"
    r = redis.get_client()
    try:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, 60)
        if count > (s.ALERT_QPS_THRESHOLD if hasattr(s, "ALERT_QPS_THRESHOLD") else 60):
            raise RateLimitError("rate limit exceeded")
    finally:
        await r.close()


@router.post("/subgraph", response_model=ApiResponse[SubgraphResult])
async def subgraph_endpoint(
    body: SubgraphReq,
    request: Request,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    _ext=Depends(require_external),
):
    await _check_rate_limit(request, redis)

    kg = KGQueryService(neo4j)
    cache_key = f"{get_settings().REDIS_KEY_PREFIX}ext:sg:{hashlib.md5(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()}"

    r = redis.get_client()
    try:
        cached = await r.get(cache_key)
        if cached:
            return ApiResponse(data=SubgraphResult.model_validate_json(cached))
    finally:
        await r.close()

    sg = await kg.query_subgraph(body.entity_name, body.depth, body.relation_types)

    r = redis.get_client()
    try:
        await r.setex(cache_key, 60, sg.model_dump_json())
    finally:
        await r.close()

    return ApiResponse(data=sg)


@router.post("/context", response_model=ApiResponse[dict])
async def context_endpoint(
    body: ContextReq,
    request: Request,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    _ext=Depends(require_external),
):
    await _check_rate_limit(request, redis)

    kg = KGQueryService(neo4j)
    context = await kg.get_entity_context(body.entity_name, body.max_neighbors)
    sg = await kg.query_subgraph(body.entity_name, depth=1)

    llm = get_chat_model()
    neighbors_yaml = json.dumps(context, ensure_ascii=False)
    prompt = f"围绕 {body.entity_name}，结合下列邻居关系总结其角色、作用、关键关联。\n{neighbors_yaml}"
    msg = await llm.ainvoke(prompt)
    summary = str(msg.content)

    return ApiResponse(
        data={
            "summary": summary,
            "neighbors": context,
            "evidence": sg.model_dump() if sg else {"nodes": [], "links": []},
        }
    )


@router.post("/cypher", response_model=ApiResponse[list[dict]])
async def cypher_endpoint(
    body: CypherReq,
    request: Request,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    _ext=Depends(require_external),
):
    await _check_rate_limit(request, redis)

    if _WRITE_KEYWORDS.search(body.cypher):
        raise InvalidInput("write operations not allowed", code=2003)

    s = get_settings()
    limit_pattern = re.compile(r"\blimit\s+\d+", re.I)
    if not limit_pattern.search(body.cypher):
        body.cypher += f" LIMIT 1000"

    import asyncio

    try:
        rows = await asyncio.wait_for(
            neo4j.execute_cypher(body.cypher, body.params),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        raise RequestTimeout("cypher query timed out")

    return ApiResponse(data=rows)


@router.post("/embed", response_model=ApiResponse[list[list[float]]])
async def embed_endpoint(
    body: EmbedReq,
    request: Request,
    redis: RedisClient = Depends(get_redis),
    _ext=Depends(require_external),
):
    await _check_rate_limit(request, redis)

    if len(body.texts) > 64:
        raise InvalidInput("max 64 texts per request")
    for t in body.texts:
        if len(t) > 8000:
            raise InvalidInput("single text exceeds 8000 chars")

    try:
        emb_model = get_embedding_model()
    except Exception as e:
        from kg_system.core.exceptions import LLMError

        raise LLMError(f"embedding model unavailable: {e}")

    embeddings = await emb_model.aembed_documents(body.texts)
    return ApiResponse(data=embeddings)
