from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from kg_system.api.deps import get_redis, require_admin
from kg_system.analysis.metrics import MetricsAggregator
from kg_system.core.exceptions import InvalidInput
from kg_system.core.models import ApiResponse
from kg_system.storage.redis_client import RedisClient

router = APIRouter(prefix="/llm", tags=["llm"])

_metrics_cache: dict = {}
_metrics_cache_ts: float = 0


class AnalyzeData(ApiResponse):
    qps: float = 0.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate: float = 0.0
    daily_cost_usd: float = 0.0


@router.get("/analyze", response_model=ApiResponse[AnalyzeData])
async def analyze_endpoint(
    window_seconds: int = Query(300, ge=60, le=86400),
    redis: RedisClient = Depends(get_redis),
    _=Depends(require_admin),
):
    import time

    window_seconds = ((window_seconds + 59) // 60) * 60

    aggregator = MetricsAggregator(redis)

    import asyncio

    qps, latencies, error_rate, daily_cost = await asyncio.gather(
        aggregator.get_qps(window_seconds),
        aggregator.get_latency_percentiles(window_seconds),
        aggregator.get_error_rate(window_seconds),
        aggregator.get_daily_cost_usd(),
    )

    return ApiResponse(
        data=AnalyzeData(
            qps=round(qps, 2),
            avg_latency_ms=round(latencies.get("p50", 0), 2),
            p99_latency_ms=round(latencies.get("p99", 0), 2),
            error_rate=round(error_rate, 4),
            daily_cost_usd=round(daily_cost, 4),
        )
    )
