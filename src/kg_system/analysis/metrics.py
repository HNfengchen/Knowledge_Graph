"""调用指标聚合（骨架占位）。"""
from __future__ import annotations

from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.storage.redis_client import RedisClient


class MetricsAggregator:
    """从 Redis Stream / Metrics 中聚合 QPS、延迟、成本等指标。"""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def get_qps(self, window_seconds: int = 60) -> float:
        raise NotImplementedInSkeleton("metrics.get_qps")

    async def get_latency_percentiles(self, window_seconds: int = 300) -> dict:
        raise NotImplementedInSkeleton("metrics.get_latency_percentiles")

    async def get_daily_cost_usd(self) -> float:
        raise NotImplementedInSkeleton("metrics.get_daily_cost_usd")
