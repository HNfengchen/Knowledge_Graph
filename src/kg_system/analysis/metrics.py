"""调用指标聚合。

从 Redis bucket Hash 和 ZSet 中计算 QPS、延迟分位数、错误率、成本。
"""
from __future__ import annotations

import time

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.storage.redis_client import RedisClient

log = get_logger(__name__)

LLM_PRICING_TABLE: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "local": {"input": 0.00, "output": 0.00},
}


class MetricsAggregator:
    """从 Redis 聚合指标。"""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._settings = get_settings()

    async def get_qps(self, window_seconds: int = 60) -> float:
        now = int(time.time())
        start_bucket = (now - window_seconds) // 60
        end_bucket = now // 60
        prefix = self._settings.REDIS_KEY_PREFIX
        metrics_prefix = self._settings.REDIS_METRICS_PREFIX

        r = self._redis.get_client()
        try:
            total_count = 0
            for bucket in range(start_bucket, end_bucket + 1):
                key = f"{prefix}{metrics_prefix}{bucket}"
                count = await r.hget(key, "count")
                if count:
                    total_count += int(count)
            return total_count / max(window_seconds, 1)
        finally:
            await r.close()

    async def get_latency_percentiles(self, window_seconds: int = 300) -> dict:
        now = int(time.time())
        start_bucket = (now - window_seconds) // 60
        end_bucket = now // 60
        prefix = self._settings.REDIS_KEY_PREFIX

        r = self._redis.get_client()
        try:
            all_durations: list[float] = []
            for bucket in range(start_bucket, end_bucket + 1):
                latency_key = f"{prefix}latency:{bucket}"
                vals = await r.zrangebyscore(latency_key, "-inf", "+inf")
                if vals:
                    all_durations.extend(float(v) for v in vals)

            if not all_durations:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

            all_durations.sort()
            n = len(all_durations)
            return {
                "p50": all_durations[int(n * 0.50)],
                "p95": all_durations[int(n * 0.95)],
                "p99": all_durations[int(n * 0.99)],
            }
        finally:
            await r.close()

    async def get_error_rate(self, window_seconds: int = 60) -> float:
        now = int(time.time())
        start_bucket = (now - window_seconds) // 60
        end_bucket = now // 60
        prefix = self._settings.REDIS_KEY_PREFIX
        metrics_prefix = self._settings.REDIS_METRICS_PREFIX

        r = self._redis.get_client()
        try:
            total_count = 0
            total_errors = 0
            for bucket in range(start_bucket, end_bucket + 1):
                key = f"{prefix}{metrics_prefix}{bucket}"
                count = await r.hget(key, "count")
                errors = await r.hget(key, "errors")
                if count:
                    total_count += int(count)
                if errors:
                    total_errors += int(errors)
            if total_count == 0:
                return 0.0
            return total_errors / total_count
        finally:
            await r.close()

    async def get_daily_cost_usd(self) -> float:
        now = int(time.time())
        start_bucket = (now - 86400) // 60
        end_bucket = now // 60
        prefix = self._settings.REDIS_KEY_PREFIX
        metrics_prefix = self._settings.REDIS_METRICS_PREFIX

        r = self._redis.get_client()
        try:
            total_input_tokens = 0
            total_output_tokens = 0
            for bucket in range(start_bucket, end_bucket + 1):
                key = f"{prefix}{metrics_prefix}{bucket}"
                pt = await r.hget(key, "total_prompt_tokens")
                ct = await r.hget(key, "total_completion_tokens")
                if pt:
                    total_input_tokens += int(pt)
                if ct:
                    total_output_tokens += int(ct)

            s = self._settings
            cost = 0.0
            for model_key, rates in LLM_PRICING_TABLE.items():
                if model_key in s.OPENAI_MODEL or model_key in s.ANTHROPIC_MODEL:
                    cost += (total_input_tokens / 1_000_000) * rates["input"]
                    cost += (total_output_tokens / 1_000_000) * rates["output"]
            if cost == 0.0:
                cost = (total_input_tokens / 1_000_000) * 0.15
                cost += (total_output_tokens / 1_000_000) * 0.60
            return cost
        finally:
            await r.close()
