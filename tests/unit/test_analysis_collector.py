from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg_system.analysis.collector import StreamCollector
from kg_system.storage.redis_client import RedisClient


@pytest.mark.unit
class TestStreamCollector:
    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        return MagicMock(spec=RedisClient)

    @pytest.fixture
    def collector(self, mock_redis: MagicMock) -> StreamCollector:
        return StreamCollector(mock_redis)

    async def test_start_creates_task(self, collector: StreamCollector) -> None:
        stop = collector._stop
        async def _run() -> None:
            while not stop.is_set():
                await asyncio.sleep(0.05)
        with patch.object(collector, "_run", _run):
            await collector.start()
            assert collector._task is not None
            assert not collector._task.done()
            await collector.stop()
            assert collector._task is None

    async def test_start_is_idempotent(self, collector: StreamCollector) -> None:
        stop = collector._stop
        async def _run() -> None:
            while not stop.is_set():
                await asyncio.sleep(0.05)
        with patch.object(collector, "_run", _run):
            await collector.start()
            first = collector._task
            await collector.start()
            assert collector._task is first
            await collector.stop()

    async def test_stop_does_nothing_when_not_running(
        self, collector: StreamCollector
    ) -> None:
        await collector.stop()
        assert collector._task is None

    def test_process_message_writes_bucket_keys(self, collector: StreamCollector) -> None:
        mock_r = MagicMock()
        pipeline = MagicMock()
        mock_r.pipeline.return_value = pipeline

        with patch("kg_system.analysis.collector.time.time", return_value=1234567890):
            collector._process_message(
                {
                    "duration_ms": "1500",
                    "prompt_tokens": "100",
                    "completion_tokens": "50",
                },
                "kg:",
                "metrics:",
                mock_r,
            )

        bucket_key = "kg:metrics:20576131"
        latency_key = "kg:latency:20576131"

        pipeline.hincrby.assert_any_call(bucket_key, "count", 1)
        pipeline.hincrby.assert_any_call(bucket_key, "total_duration", 1500)
        pipeline.hincrby.assert_any_call(bucket_key, "total_prompt_tokens", 100)
        pipeline.hincrby.assert_any_call(bucket_key, "total_completion_tokens", 50)
        pipeline.hincrby.assert_any_call(bucket_key, "errors", 0)
        pipeline.execute.assert_called_once()

        mock_r.zadd.assert_called_once_with(latency_key, {"1234567890": 1500.0})
        mock_r.expire.assert_any_call(bucket_key, 604800)
        mock_r.expire.assert_any_call(latency_key, 604800)

    def test_process_message_sets_error_flag(self, collector: StreamCollector) -> None:
        mock_r = MagicMock()
        pipeline = MagicMock()
        mock_r.pipeline.return_value = pipeline

        with patch("kg_system.analysis.collector.time.time", return_value=1234567890):
            collector._process_message(
                {
                    "duration_ms": "500",
                    "prompt_tokens": "50",
                    "completion_tokens": "25",
                    "error": "rate_limit",
                },
                "kg:",
                "metrics:",
                mock_r,
            )

        pipeline.hincrby.assert_any_call("kg:metrics:20576131", "errors", 1)

    def test_process_message_writes_latency_zset(
        self, collector: StreamCollector
    ) -> None:
        mock_r = MagicMock()
        pipeline = MagicMock()
        mock_r.pipeline.return_value = pipeline

        with patch("kg_system.analysis.collector.time.time", return_value=1234567890):
            collector._process_message(
                {
                    "duration_ms": "2000",
                    "prompt_tokens": "10",
                    "completion_tokens": "5",
                },
                "kg:",
                "metrics:",
                mock_r,
            )

        mock_r.zadd.assert_called_once_with(
            "kg:latency:20576131", {"1234567890": 2000.0}
        )

    def test_process_message_skips_non_llm_events(
        self, collector: StreamCollector
    ) -> None:
        mock_r = MagicMock()
        collector._process_message(
            {"type": "embedding", "duration_ms": "100"}, "kg:", "metrics:", mock_r
        )
        mock_r.pipeline.assert_not_called()
        mock_r.zadd.assert_not_called()

    def test_process_message_defaults_fields(self, collector: StreamCollector) -> None:
        mock_r = MagicMock()
        pipeline = MagicMock()
        mock_r.pipeline.return_value = pipeline

        with patch("kg_system.analysis.collector.time.time", return_value=1000000):
            collector._process_message({}, "kg:", "metrics:", mock_r)

        pipeline.hincrby.assert_any_call("kg:metrics:16666", "count", 1)
        pipeline.hincrby.assert_any_call("kg:metrics:16666", "total_duration", 0)
        pipeline.hincrby.assert_any_call("kg:metrics:16666", "total_prompt_tokens", 0)
        pipeline.hincrby.assert_any_call("kg:metrics:16666", "total_completion_tokens", 0)
        pipeline.hincrby.assert_any_call("kg:metrics:16666", "errors", 0)
        pipeline.execute.assert_called_once()
        mock_r.zadd.assert_called_once_with("kg:latency:16666", {"1000000": 0.0})

    async def test_ensure_group_creates_group(self, collector: StreamCollector) -> None:
        mock_r = AsyncMock()
        await collector._ensure_group(mock_r, "test_stream", "test_group")
        mock_r.xgroup_create.assert_awaited_once_with(
            "test_stream", "test_group", id="0", mkstream=True
        )

    async def test_ensure_group_silent_when_exists(
        self, collector: StreamCollector
    ) -> None:
        mock_r = AsyncMock()
        mock_r.xgroup_create.side_effect = Exception("BUSYGROUP group already exists")
        await collector._ensure_group(mock_r, "test_stream", "test_group")
        mock_r.xgroup_create.assert_awaited_once()
