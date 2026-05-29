from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


# —— 抽取阶段中间表示 ——
class ExtractedEntity(BaseModel):
    name: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    source_chunk_id: str | None = None


class ExtractedRelation(BaseModel):
    head: str
    tail: str
    relation: str
    props: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


# —— 出库后给前端的图结构 ——
class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphLink(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0


class SubgraphResult(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)


# —— HTTP 包装 ——
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    msg: str = "success"
    data: T | None = None


# —— 告警 ——
class Alert(BaseModel):
    rule: str
    severity: str
    message: str
    metrics: dict[str, Any] = Field(default_factory=dict)
