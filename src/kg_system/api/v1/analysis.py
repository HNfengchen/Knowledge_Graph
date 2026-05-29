from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from kg_system.api.deps import require_admin
from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import ApiResponse

router = APIRouter(prefix="/llm", tags=["analysis"])


class AnalyzeData(BaseModel):
    qps: float
    avg_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    daily_cost_usd: float


@router.get("/analyze", response_model=ApiResponse[AnalyzeData])
async def analyze_endpoint(
    window_seconds: int = Query(300, ge=60, le=86400),
    _admin=Depends(require_admin),
):
    raise NotImplementedInSkeleton("/llm/analyze")
