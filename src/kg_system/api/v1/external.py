from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kg_system.api.deps import require_external
from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import ApiResponse, SubgraphResult

router = APIRouter(prefix="/kg/external", tags=["external"])


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


@router.post("/subgraph", response_model=ApiResponse[SubgraphResult])
async def subgraph_endpoint(body: SubgraphReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/subgraph")


@router.post("/context", response_model=ApiResponse[dict])
async def context_endpoint(body: ContextReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/context")


@router.post("/cypher", response_model=ApiResponse[list[dict]])
async def cypher_endpoint(body: CypherReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/cypher")


@router.post("/embed", response_model=ApiResponse[list[list[float]]])
async def embed_endpoint(body: EmbedReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/embed")
