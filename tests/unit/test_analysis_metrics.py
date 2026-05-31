from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg_system.analysis.metrics import LLM_PRICING_TABLE, MetricsAggregator
from kg_system.storage.redis_client import RedisClient


@pytest.mark.unit
class TestMetricsAggregator:
    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        return MagicMock(spec=RedisClient)

    @pytest.fixture
    def aggregator(self, mock_redis: MagicMock) -> MetricsAggregator:
        return MetricsAggregator(mock_redis)

    async def test_get_qps_calculates_correctly(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        async def hget_side_effect(key: str, field: str) -> str | None:
            if field == "count":
                if "metrics:59" in key:
                    return "10"
                if "metrics:60" in key:
                    return "20"
            return None

        mock_r.hget.side_effect = hget_side_effect

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            qps = await aggregator.get_qps(60)

        assert qps == pytest.approx(0.5)
        mock_r.close.assert_awaited_once()

    async def test_get_qps_returns_zero_when_no_data(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r
        mock_r.hget.return_value = None

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            qps = await aggregator.get_qps(60)

        assert qps == 0.0

    async def test_get_qps_handles_zero_window(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r
        mock_r.hget.return_value = "100"

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            qps = await aggregator.get_qps(0)

        assert qps == 100.0

    async def test_get_latency_percentiles_calculates_correctly(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        mock_r.zrangebyscore.return_value = ["100", "200", "300", "400", "500"]

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            result = await aggregator.get_latency_percentiles(300)

        assert result == {"p50": 300.0, "p95": 500.0, "p99": 500.0}
        mock_r.close.assert_awaited_once()

    async def test_get_latency_percentiles_returns_zeros_when_no_data(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r
        mock_r.zrangebyscore.return_value = []

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            result = await aggregator.get_latency_percentiles(300)

        assert result == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    async def test_get_latency_percentiles_merges_multiple_buckets(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        async def zrange_side_effect(
            key: str, min_score: str, max_score: str
        ) -> list[str]:
            if "latency:59" in key:
                return ["10", "20"]
            if "latency:60" in key:
                return ["30", "40", "50"]
            return []

        mock_r.zrangebyscore.side_effect = zrange_side_effect

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            result = await aggregator.get_latency_percentiles(60)

        assert result == {"p50": 30.0, "p95": 50.0, "p99": 50.0}

    async def test_get_error_rate_calculates_correctly(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        async def hget_side_effect(key: str, field: str) -> str | None:
            if "metrics:" not in key:
                return None
            if field == "count":
                return "100"
            if field == "errors":
                return "5"
            return None

        mock_r.hget.side_effect = hget_side_effect

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            rate = await aggregator.get_error_rate(60)

        assert rate == pytest.approx(0.05)

    async def test_get_error_rate_returns_zero_when_no_data(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r
        mock_r.hget.return_value = None

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            rate = await aggregator.get_error_rate(60)

        assert rate == 0.0

    async def test_get_error_rate_returns_zero_when_zero_count(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        async def hget_side_effect(key: str, field: str) -> str | None:
            if field == "count":
                return "0"
            return None

        mock_r.hget.side_effect = hget_side_effect

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            rate = await aggregator.get_error_rate(60)

        assert rate == 0.0

    async def test_get_daily_cost_usd_returns_zero_when_no_data(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r
        mock_r.hget.return_value = None

        with patch("kg_system.analysis.metrics.time.time", return_value=86400):
            cost = await aggregator.get_daily_cost_usd()

        assert cost == 0.0

    async def test_get_daily_cost_usd_calculates_correctly(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        async def hget_side_effect(key: str, field: str) -> str | None:
            if "metrics:" not in key:
                return None
            if "metrics:1440" not in key:
                return None
            if field == "total_prompt_tokens":
                return "1000000"
            if field == "total_completion_tokens":
                return "500000"
            return None

        mock_r.hget.side_effect = hget_side_effect

        with patch(
            "kg_system.analysis.metrics.LLM_PRICING_TABLE",
            {"gpt-4o-mini": {"input": 0.15, "output": 0.60}},
        ):
            with patch("kg_system.analysis.metrics.time.time", return_value=86400):
                cost = await aggregator.get_daily_cost_usd()

        cost = round(cost, 6)
        assert cost == 0.45

    async def test_get_daily_cost_usd_fallback_pricing(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r

        async def hget_side_effect(key: str, field: str) -> str | None:
            if "metrics:" not in key:
                return None
            if "metrics:1440" not in key:
                return None
            if field == "total_prompt_tokens":
                return "1000000"
            if field == "total_completion_tokens":
                return "500000"
            return None

        mock_r.hget.side_effect = hget_side_effect

        with patch(
            "kg_system.analysis.metrics.LLM_PRICING_TABLE",
            {"nonexistent-model": {"input": 0.0, "output": 0.0}},
        ):
            with patch("kg_system.analysis.metrics.time.time", return_value=86400):
                cost = await aggregator.get_daily_cost_usd()

        cost = round(cost, 6)
        assert cost == 0.45

    async def test_close_called_on_each_method(
        self, aggregator: MetricsAggregator, mock_redis: MagicMock
    ) -> None:
        mock_r = AsyncMock()
        mock_redis.get_client.return_value = mock_r
        mock_r.hget.return_value = None
        mock_r.zrangebyscore.return_value = []

        with patch("kg_system.analysis.metrics.time.time", return_value=3600):
            await aggregator.get_qps(60)
            await aggregator.get_latency_percentiles(300)
            await aggregator.get_error_rate(60)
            await aggregator.get_daily_cost_usd()

        assert mock_r.close.await_count == 4
